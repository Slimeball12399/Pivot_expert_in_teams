import json
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from aiortc import RTCPeerConnection, RTCSessionDescription
from django.test import SimpleTestCase, override_settings

from live import runtime
from live.models import Connection
from live.Services.AudioService import AudioService
from live.Services.CommandsService import CommandsService
from live.Services.ConnectionService import CONNECTION_NOT_FOUND, NOT_WAITING_FOR_ANSWER, ConnectionService
from live.views import INVALID_BODY, NOT_RECORDING, UNAUTHORIZED

TOKEN = "test-token"
HEADERS = {"X-Live-Token": TOKEN}

# The live process's internal API (live/views.py), with its own URLconf and
# no middleware, as pivot/settings_live.py has them. The services are fresh
# for each test, on a temporary folder. The offer and answer are real: a
# second aiortc peer plays the browser. What the services do with them is
# tested in their own files.


@override_settings(ROOT_URLCONF="live.urls", MIDDLEWARE=[], LIVE_INTERNAL_TOKEN=TOKEN)
class InternalApiTests(SimpleTestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.audio = AudioService(Path(folder.name))
        self.addCleanup(self.audio.close)
        self.connections = ConnectionService(
            ice_servers=[], commands=CommandsService(self.audio), audio=self.audio)
        for name, service in [("AUDIO", self.audio), ("CONNECTIONS", self.connections)]:
            patcher = mock.patch.object(runtime, name, service)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.session_id = uuid.uuid4()
        self.user_id = uuid.uuid4()

    def body(self, **overrides):
        return {"session_id": str(self.session_id), "user_id": str(self.user_id),
                "kind": Connection.Kind.TRAINER_AUDIO, **overrides}

    async def post(self, path, body=None, headers=HEADERS):
        data = body if isinstance(body, str) else json.dumps(body or {})
        return await self.async_client.post(path, data=data, content_type="application/json",
                                            headers=headers)

    async def test_needs_the_token(self):
        for path in ["/offer/", "/answer/", f"/sessions/{self.session_id}/close/",
                     f"/talks/{uuid.uuid4()}/stop-recording/"]:
            for label, headers in [("none", {}), ("wrong", {"X-Live-Token": "nope"})]:
                with self.subTest(path, token=label):
                    response = await self.post(path, self.body(), headers=headers)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.json()["code"], UNAUTHORIZED)
        self.assertEqual(self.connections.connections, {})

    async def test_only_post(self):
        response = await self.async_client.get("/offer/", headers=HEADERS)
        self.assertEqual(response.status_code, 405)

    async def test_offer_and_answer(self):
        browser = RTCPeerConnection()
        try:
            response = await self.post("/offer/", self.body())
            with self.subTest("offer: the mic to receive, and the control channel"):
                self.assertEqual(response.status_code, 200)
                sdp = response.json()["sdp"]
                self.assertIn("m=audio", sdp)
                self.assertIn("a=recvonly", sdp)
                self.assertIn("m=application", sdp)
                connection = self.connections.connections[(self.session_id, Connection.Kind.TRAINER_AUDIO)]
                self.assertEqual(connection.state, Connection.State.WAITING_FOR_ANSWER)

            await browser.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
            await browser.setLocalDescription(await browser.createAnswer())
            answer = self.body(sdp=browser.localDescription.sdp)

            with self.subTest("someone else's answer: not found"):
                response = await self.post("/answer/", {**answer, "user_id": str(uuid.uuid4())})
                self.assertEqual((response.status_code, response.json()["code"]), (404, CONNECTION_NOT_FOUND))
            with self.subTest("the answer: accepted, connecting"):
                response = await self.post("/answer/", answer)
                self.assertEqual(response.status_code, 204)
                self.assertIn(connection.state, (Connection.State.CONNECTING, Connection.State.CONNECTED))
            with self.subTest("a second answer: refused"):
                response = await self.post("/answer/", answer)
                self.assertEqual((response.status_code, response.json()["code"]), (409, NOT_WAITING_FOR_ANSWER))
        finally:
            await self.connections.close_session(self.session_id)
            await browser.close()

    async def test_rejects_bad_bodies(self):
        # (label, path, body, the field the error is on)
        cases = [
            ("not JSON", "/offer/", "hello", "body"),
            ("no kind", "/offer/", self.body(kind=None), "kind"),
            ("not a session id", "/offer/", self.body(session_id="abc"), "session_id"),
            ("an unknown kind", "/offer/", self.body(kind="VIDEO"), "kind"),
            ("an answer without sdp", "/answer/", self.body(), "sdp"),
            ("an empty sdp", "/answer/", self.body(sdp=""), "sdp"),
        ]
        for label, path, body, field in cases:
            with self.subTest(label):
                response = await self.post(path, body)
                self.assertEqual((response.status_code, response.json()["code"]), (400, INVALID_BODY))
                self.assertIn(field, response.json()["errors"])
        with self.subTest("not a talk id in the URL: no such URL"):
            response = await self.post("/talks/abc/stop-recording/")
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.connections.connections, {})

    async def test_close_session(self):
        url = f"/sessions/{self.session_id}/close/"
        with self.subTest("no connections: fine, closed is false"):
            response = await self.post(url)
            self.assertEqual((response.status_code, response.json()), (200, {"closed": False}))
        with self.subTest("after an offer: closed and gone"):
            await self.post("/offer/", self.body())
            response = await self.post(url)
            self.assertEqual(response.json(), {"closed": True})
            self.assertEqual(self.connections.connections, {})

    async def test_stop_recording(self):
        talk_id = uuid.uuid4()
        recording = self.audio.start_recording(self.session_id, talk_id)
        url = f"/talks/{talk_id}/stop-recording/"
        with self.subTest("recording: stopped, its PCM relative to FILES_DIR"):
            response = await self.post(url)
            self.assertEqual((response.status_code, response.json()),
                             (200, {"talk_id": str(talk_id), "path": f"recordings/{talk_id}.pcm"}))
            self.assertTrue(recording.file.closed)
        with self.subTest("again: not recording any more"):
            response = await self.post(url)
            self.assertEqual((response.status_code, response.json()["code"]), (404, NOT_RECORDING))
