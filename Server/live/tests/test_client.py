import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from live.client import LIVE_UNAVAILABLE, LiveClient, LiveError
from live.models import Connection

# Django's client for the live process's internal API (live/client.py),
# against a small HTTP server on localhost that plays the live process: it
# records each request and answers what the test set. What the live process
# itself answers is tested in test_views.py.

TOKEN = "test-token"


class FakeLive(BaseHTTPRequestHandler):
    """Records the request on the server and answers server.reply:
    (status, body), the body as JSON (None: no body)."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.server.requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": json.loads(self.rfile.read(length) or b"null"),
        })
        status, body = self.server.reply
        content = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass  # no request lines in the test output


@override_settings(LIVE_INTERNAL_TOKEN=TOKEN, FILES_DIR=Path("/srv/files"),
                   RTC_ICE_SERVERS=[], TURN_SECRET="", RTC_RELAY_ONLY=False)
class LiveClientTests(SimpleTestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeLive)
        self.server.requests = []
        self.server.reply = (200, {})
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        with override_settings(LIVE_INTERNAL_URL=f"http://127.0.0.1:{self.server.server_port}"):
            self.live = LiveClient(timeout=5)
        self.session_id, self.user_id, self.talk_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def last(self):
        return self.server.requests[-1]

    def test_offer(self):
        self.server.reply = (200, {"sdp": "v=0\r\n"})
        offer = self.live.offer(self.session_id, self.user_id, Connection.Kind.TRAINER_AUDIO)
        self.assertEqual(offer, {"sdp": "v=0\r\n", "ice_servers": [], "ice_transport_policy": "all"})
        with self.subTest("the body and the token"):
            self.assertEqual(self.last()["path"], "/offer/")
            self.assertEqual(self.last()["body"], {
                "session_id": str(self.session_id), "user_id": str(self.user_id), "kind": "TRAINER_AUDIO"})
            self.assertEqual(self.last()["headers"]["X-Live-Token"], TOKEN)
            self.assertEqual(self.last()["headers"]["Content-Type"], "application/json")

    @override_settings(RTC_ICE_SERVERS=["stun:203.0.113.7:3478", "turn:203.0.113.7:3478"],
                       TURN_SECRET="secret", RTC_RELAY_ONLY=True)
    def test_offer_ice_servers(self):
        self.server.reply = (200, {"sdp": "v=0\r\n"})
        offer = self.live.offer(self.session_id, self.user_id, Connection.Kind.TRAINER_AUDIO)
        stun, turn = offer["ice_servers"]
        self.assertEqual(stun, {"urls": "stun:203.0.113.7:3478"})
        with self.subTest("TURN with a login of its own, named after the user"):
            self.assertEqual(turn["urls"], "turn:203.0.113.7:3478")
            self.assertTrue(turn["username"].endswith(f":{self.user_id}"))
            self.assertTrue(turn["credential"])
        self.assertEqual(offer["ice_transport_policy"], "relay")

    @override_settings(RTC_ICE_SERVERS=["turn:203.0.113.7:3478"], TURN_SECRET="")
    def test_offer_turn_without_a_secret_is_left_out(self):
        self.server.reply = (200, {"sdp": "v=0\r\n"})
        offer = self.live.offer(self.session_id, self.user_id, Connection.Kind.TRAINER_AUDIO)
        self.assertEqual(offer["ice_servers"], [])

    def test_answer(self):
        self.server.reply = (204, None)
        result = self.live.answer(self.session_id, self.user_id, Connection.Kind.TRAINER_AUDIO, "v=0\r\n")
        self.assertIsNone(result)
        self.assertEqual(self.last()["path"], "/answer/")
        self.assertEqual(self.last()["body"]["sdp"], "v=0\r\n")  # kept exactly, line break and all

    def test_close_session(self):
        self.server.reply = (200, {"closed": True})
        self.assertIs(self.live.close_session(self.session_id), True)
        self.assertEqual(self.last()["path"], f"/sessions/{self.session_id}/close/")

    def test_stop_recording(self):
        self.server.reply = (200, {"talk_id": str(self.talk_id), "path": f"recordings/{self.talk_id}.pcm"})
        path = self.live.stop_recording(self.talk_id)
        self.assertEqual(path, Path("/srv/files") / "recordings" / f"{self.talk_id}.pcm")
        self.assertEqual(self.last()["path"], f"/talks/{self.talk_id}/stop-recording/")

    def test_the_live_process_errors(self):
        cases = [
            (404, "connection_not_found", "No connection is waiting for this answer."),
            (409, "not_waiting_for_answer", "This connection has its answer already."),
            (401, "unauthorized", "Missing or wrong X-Live-Token."),
        ]
        for status, code, detail in cases:
            with self.subTest(code):
                self.server.reply = (status, {"code": code, "detail": detail})
                with self.assertRaises(LiveError) as caught:
                    self.live.answer(self.session_id, self.user_id, Connection.Kind.TRAINER_AUDIO, "v=0\r\n")
                self.assertEqual((caught.exception.status, caught.exception.code, caught.exception.detail),
                                 (status, code, detail))

    def test_unavailable(self):
        with self.subTest("an error that isn't the live process's (a proxy's 502)"):
            self.server.reply = (502, b"<html>Bad gateway</html>")
            with self.assertRaises(LiveError) as caught:
                self.live.close_session(self.session_id)
            self.assertEqual((caught.exception.code, caught.exception.status), (LIVE_UNAVAILABLE, None))

        with self.subTest("an answer that isn't JSON"):
            self.server.reply = (200, b"not json")
            with self.assertRaises(LiveError) as caught:
                self.live.close_session(self.session_id)
            self.assertEqual(caught.exception.code, LIVE_UNAVAILABLE)

        with self.subTest("nothing listening"):
            port = self.server.server_port
            self.server.shutdown()
            self.server.server_close()
            with self.assertRaises(LiveError) as caught:
                LiveClient(base_url=f"http://127.0.0.1:{port}", timeout=2).close_session(self.session_id)
            self.assertEqual(caught.exception.code, LIVE_UNAVAILABLE)
            self.assertEqual(caught.exception.detail, "The live process can't be reached.")
