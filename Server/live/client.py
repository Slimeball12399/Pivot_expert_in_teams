"""Django's client for the live process's internal API (live/views.py): what
the web process calls to set up a trainer's WebRTC connection, close a
session's connections and stop a talk's recording. Used by the web views;
the live process itself never imports it.

  client = LiveClient()                                   # LIVE_INTERNAL_URL and _TOKEN
  offer = client.offer(session.id, user.id, Connection.Kind.TRAINER_AUDIO)  # for the browser
  client.answer(session.id, user.id, Connection.Kind.TRAINER_AUDIO, answer_sdp)
  client.close_session(session.id)                        # -> True if there were connections
  path = client.stop_recording(talk.id)                   # -> the PCM under FILES_DIR

The caller has already checked who the user is and that they may do it; the
live process trusts the token, not the user. The browser's side of the
connection comes from here too: offer() adds the ICE servers it is to use,
with a TURN login of its own (live/turn.py), so the views only pass it on. Every failure is a LiveError:
the live process's own {"code", "detail"} with its HTTP status (404 nothing
found, 409 wrong state, ...), or LIVE_UNAVAILABLE (status None) when it
can't be reached or answers something that isn't its API.

Plain urllib, so nothing to install; synchronous like the web views. Proxy
settings in the environment (HTTP_PROXY, ...) are ignored: the live process
is always on the local or Docker network.
"""

import json
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from django.conf import settings

from live.models import Connection
from live.turn import BROWSER_TTL_SECONDS, turn_credentials

# The code of a LiveError when there is no answer from the live process's API.
LIVE_UNAVAILABLE = "live_unavailable"


class LiveError(Exception):
    """A call to the live process that didn't work. code: the live process's
    error code (live/views.py and its services) or LIVE_UNAVAILABLE; status:
    its HTTP status, None when unavailable; detail: a sentence for the log or
    the user."""

    def __init__(self, code: str, detail: str, status: int | None = None):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


class LiveClient:
    """The live process's internal API, one method per endpoint. Cheap to
    make: make one where it is needed, so it follows the settings (tests
    override them)."""

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 15):
        self.base_url = (base_url or settings.LIVE_INTERNAL_URL).rstrip("/")
        self.token = token if token is not None else settings.LIVE_INTERNAL_TOKEN
        # Long enough for an offer: the live process gathers every ICE
        # candidate (STUN and TURN included) before it answers.
        self.timeout = timeout
        # No proxy handler: never through HTTP_PROXY and the like.
        self.opener = build_opener(ProxyHandler({}))

    def offer(self, session_id: uuid.UUID, user_id: uuid.UUID, kind: Connection.Kind) -> dict:
        """A new peer connection for this session and kind (an older one is
        replaced) and what the browser needs to answer it, within the live
        process's offer timeout (30 s): {"sdp", "ice_servers",
        "ice_transport_policy"}, as RTCPeerConnection takes them.

        ice_servers is RTC_ICE_SERVERS, a TURN server with a login made for
        this user (valid BROWSER_TTL_SECONDS, named after the user id); without
        TURN_SECRET there is no login, so the TURN server is left out.
        ice_transport_policy is "relay" with RTC_RELAY_ONLY, else "all"."""
        data = self.post("/offer/", {
            "session_id": str(session_id), "user_id": str(user_id), "kind": str(kind)})
        ice_servers = []
        for url in settings.RTC_ICE_SERVERS:
            if not url.startswith(("turn:", "turns:")):
                ice_servers.append({"urls": url})
            elif settings.TURN_SECRET:
                username, credential = turn_credentials(settings.TURN_SECRET, str(user_id), BROWSER_TTL_SECONDS)
                ice_servers.append({"urls": url, "username": username, "credential": credential})
        return {
            "sdp": data["sdp"],
            "ice_servers": ice_servers,
            "ice_transport_policy": "relay" if settings.RTC_RELAY_ONLY else "all",
        }

    def answer(self, session_id: uuid.UUID, user_id: uuid.UUID, kind: Connection.Kind, sdp: str) -> None:
        """The browser's answer to the offer for this session, user and kind.
        Errors: connection_not_found (404: no offer, expired, or another
        user's), not_waiting_for_answer and connection_replaced (409)."""
        self.post("/answer/", {
            "session_id": str(session_id), "user_id": str(user_id), "kind": str(kind), "sdp": sdp})

    def close_session(self, session_id: uuid.UUID) -> bool:
        """Closes the session's connections (it ended or was aborted); fine
        when there are none. Returns whether there were."""
        return self.post(f"/sessions/{session_id}/close/")["closed"]

    def stop_recording(self, talk_id: uuid.UUID) -> Path:
        """Stops the talk's recording (finished or discarded) and returns
        where its PCM is: under this process's FILES_DIR (the live process
        sends it relative to the shared folder). Error: not_recording (404)."""
        data = self.post(f"/talks/{talk_id}/stop-recording/")
        return settings.FILES_DIR / data["path"]

    def post(self, path: str, body: dict | None = None) -> dict | None:
        """POSTs the body as JSON with the token and returns the JSON answer
        (None for 204). Raises LiveError for an error answer or none."""
        request = Request(
            self.base_url + path, method="POST",
            data=json.dumps(body or {}).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     "X-Live-Token": self.token})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                content = response.read()
                return json.loads(content) if content else None
        except HTTPError as error:
            # The live process's own errors are {"code", "detail"}; anything
            # else (a 502 from something in between) means it isn't there.
            try:
                data = json.loads(error.read())
                code, detail = data["code"], data["detail"]
            except (ValueError, KeyError, TypeError):
                raise LiveError(LIVE_UNAVAILABLE, f"The live process answered {error.code}.") from error
            raise LiveError(code, detail, error.code) from error
        except (URLError, OSError, ValueError) as error:
            # Not running, refused, timed out, or an answer that isn't JSON.
            raise LiveError(LIVE_UNAVAILABLE, "The live process can't be reached.") from error
