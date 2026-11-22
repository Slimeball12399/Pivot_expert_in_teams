"""The live process's objects. Not database models: a WebRTC connection only
exists in the live process's memory (ConnectionService owns them, see
Services/ConnectionService.py), so Connection is a plain class, and there is
nothing to migrate."""

import asyncio
import uuid
from datetime import datetime
from enum import StrEnum

from aiortc import RTCDataChannel, RTCPeerConnection


class Connection:
    """One peer connection of a session, and what the live process knows
    about it. Its methods only change the connection itself; ConnectionService
    decides when (who may connect, answer, replace or close it)."""

    class Kind(StrEnum):
        TRAINER_AUDIO = "TRAINER_AUDIO"  # the trainer's browser: mic in, feedback out
        SPEAKER_FEEDBACK = "SPEAKER_FEEDBACK"  # the speaker's phone: feedback out only (later)

    class State(StrEnum):
        WAITING_FOR_ANSWER = "WAITING_FOR_ANSWER"  # offer made, no answer yet
        CONNECTING = "CONNECTING"  # answer set, ICE and DTLS still running
        CONNECTED = "CONNECTED"
        DISCONNECTED = "DISCONNECTED"  # dropped; the browser is expected to reconnect

    def __init__(self, session_id: uuid.UUID, user_id: uuid.UUID, kind: Kind,
                 peer: RTCPeerConnection, channel: RTCDataChannel, now: datetime):
        self.session_id = session_id
        # The only user who may answer this connection's offer.
        self.user_id = user_id
        self.kind = kind
        self.peer = peer
        # "control": talk commands in, feedback out.
        self.channel = channel
        self.state = Connection.State.WAITING_FOR_ANSWER
        self.created_at = now
        # The first time it connected, and the last time it dropped.
        self.connected_at: datetime | None = None
        self.disconnected_at: datetime | None = None
        # Throws the offer away when it isn't connected in time; cancelled once it is.
        self.expiry: asyncio.Task | None = None

    @property
    def key(self) -> tuple[uuid.UUID, Kind]:
        """Its place in ConnectionService.connections: one per session and kind."""
        return (self.session_id, self.kind)

    def mark_answered(self):
        """The browser's answer is being set: no second one is accepted."""
        self.state = Connection.State.CONNECTING

    def mark_connected(self, now: datetime):
        """ICE and DTLS are through: it carries data, and the offer no longer expires."""
        self.state = Connection.State.CONNECTED
        self.connected_at = self.connected_at or now
        if self.expiry is not None:
            self.expiry.cancel()

    def mark_disconnected(self, now: datetime):
        """The connection was lost (aiortc reports "failed"); the peer can't
        recover, the browser asks for a new offer."""
        self.state = Connection.State.DISCONNECTED
        self.disconnected_at = now

    async def close(self):
        """Stops the expiry and closes the peer (media and data channel)."""
        if self.expiry is not None:
            self.expiry.cancel()
        await self.peer.close()

    def __str__(self):
        return f"Connection {self.kind} of session {self.session_id} {self.state}"
