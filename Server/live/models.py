"""The live process's objects. Not database models: a WebRTC connection and
a talk's recording only exist in the live process's memory (ConnectionService
and AudioService own them, see Services/), so they are plain classes, and
there is nothing to migrate."""

import asyncio
import os
import uuid
from collections import deque
from datetime import datetime
from enum import StrEnum
from pathlib import Path

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
        # Reads the trainer's audio track (AudioService.read), while it lasts.
        self.audio_task: asyncio.Task | None = None

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
        """Stops the expiry and the audio reading, and closes the peer (media
        and data channel). The session's recording stays: a reconnect goes on
        writing into it."""
        if self.expiry is not None:
            self.expiry.cancel()
        if self.audio_task is not None:
            self.audio_task.cancel()
        await self.peer.close()

    def __str__(self):
        return f"Connection {self.kind} of session {self.session_id} {self.state}"


class Recording:
    """One talk's audio as the live process receives it: raw PCM appended to
    a file, and the last window_seconds of it in memory for the live voice
    windows. Its methods only change the recording itself; AudioService
    decides when (which talk, when to start, pause and finish).

    The file is raw PCM, 16-bit little-endian, mono, at the AudioService's
    rate, with no header: append-only, so a restart of the live process loses
    at most what wasn't synced yet. A WAV header goes on when the talk is done.
    """

    class State(StrEnum):
        RECORDING = "RECORDING"  # frames are written
        PAUSED = "PAUSED"  # frames are read and dropped: paused time isn't recorded

    def __init__(self, talk_id: uuid.UUID, path: Path, window_bytes: int, now: datetime):
        self.talk_id = talk_id
        self.path = path
        # Append: a talk that goes on after a restart continues the same file.
        self.file = path.open("ab")
        self.state = Recording.State.RECORDING
        # The rolling window: (receive time, PCM) per frame, oldest first,
        # at most window_bytes of PCM in total.
        self.window: deque[tuple[datetime, bytes]] = deque()
        self.window_bytes = window_bytes
        self.buffered_bytes = 0
        # When the last frame was written (UTC): where a pause after a drop
        # really started.
        self.last_frame_at: datetime | None = None
        # When the file was last synced to the disk.
        self.synced_at = now

    def write(self, pcm: bytes, now: datetime):
        """Appends a frame's PCM to the file and the window, dropping the
        oldest frames from the window past window_bytes. Nothing while paused."""
        if self.state != Recording.State.RECORDING:
            return
        self.file.write(pcm)
        self.window.append((now, pcm))
        self.buffered_bytes += len(pcm)
        while self.buffered_bytes > self.window_bytes:
            self.buffered_bytes -= len(self.window.popleft()[1])
        self.last_frame_at = now

    def pause(self):
        """Stops writing. The window is emptied: no window may hold audio from
        both sides of a pause."""
        self.state = Recording.State.PAUSED
        self.window.clear()
        self.buffered_bytes = 0

    def resume(self):
        """Writes again, into the same file; the window fills up from empty."""
        self.state = Recording.State.RECORDING

    def current_window(self) -> tuple[datetime, bytes] | None:
        """The window as it is now: when its first frame arrived (UTC, the
        PartialVoiceResult's start_at) and its PCM. None while it is empty.
        Shorter than window_bytes until that much has been recorded since
        the start or the last pause."""
        if not self.window:
            return None
        return (self.window[0][0], b"".join(pcm for _, pcm in self.window))

    def flush(self, now: datetime) -> int:
        """Hands what was written to the operating system and returns the
        file descriptor, for AudioService to fsync outside the event loop."""
        self.file.flush()
        self.synced_at = now
        return self.file.fileno()

    def close(self):
        """Flushes, syncs and closes the file (the talk is done, or the live
        process stops)."""
        self.file.flush()
        os.fsync(self.file.fileno())
        self.file.close()

    def __str__(self):
        return f"Recording of talk {self.talk_id} {self.state}"
