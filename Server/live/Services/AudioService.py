"""The audio of the trainer's connection: read from its track, resampled,
and written to the talk's recording (live.models.Recording) while the talk is
recording.

One AudioService per live process, made by run_live: it owns the recordings,
one per talk. They are kept by session: the reading task only knows its
connection, and a connection belongs to a session, which has at most one
open talk, so that is the talk it writes into. A recording outlives
the connection: after a drop and a reconnect, the new connection's track goes
on writing into the same file.

The track is always read, recording or not: aiortc only keeps the audio
flowing (and its buffers small) when someone takes the frames. While no talk
records, or it is paused, the frames are dropped.

Not wired up yet: who starts, pauses, resumes and finishes a recording (the
talk commands), and who reads current_window() every few seconds (the live
voice analysis), come next.
"""

import asyncio
import logging
import os
import uuid
from datetime import timedelta
from pathlib import Path

import av
from aiortc.mediastreams import MediaStreamError, MediaStreamTrack
from django.utils import timezone

from live.models import Connection, Recording

logger = logging.getLogger(__name__)

# What every recording is in: 16-bit samples, mono, SAMPLE_RATE per second,
# whatever the browser sends (Opus, usually 48 kHz). A reconnect can bring
# another input format; each track gets its own resampler.
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2


class AudioService:
    """The live process's talk recordings, and reading the audio into them."""

    def __init__(self, files_dir: Path, window_seconds: float = 30, sync_seconds: float = 1):
        # Where the recordings go: <files_dir>/recordings/<talk id>.pcm
        # (settings.FILES_DIR, the folder the web and live processes share).
        self.recordings_dir = files_dir / "recordings"
        # How much audio the rolling window keeps, for the live voice windows.
        self.window_bytes = int(window_seconds * SAMPLE_RATE * BYTES_PER_SAMPLE)
        # How often a recording is synced to the disk: what a crash can lose at most.
        self.sync_interval = timedelta(seconds=sync_seconds)
        # The current recordings (one per talk), by the session the talk is in.
        self.recordings: dict[uuid.UUID, Recording] = {}

    def start_recording(self, session_id: uuid.UUID, talk_id: uuid.UUID) -> Recording:
        """Starts the talk's recording (or continues its file, after a
        restart of the live process). The session's previous recording, if
        one is still there, is closed first: a session records one talk at a time."""
        old = self.recordings.pop(session_id, None)
        if old is not None:
            old.close()
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        recording = Recording(talk_id=talk_id, path=self.recordings_dir / f"{talk_id}.pcm",
                              window_bytes=self.window_bytes, now=timezone.now())
        self.recordings[session_id] = recording
        return recording

    def finish_recording(self, talk_id: uuid.UUID) -> Recording | None:
        """Stops the talk's recording (the talk was finished or discarded):
        closes and syncs its file and hands it back (its path holds the PCM),
        or None when that talk isn't recording. Only that talk: a talk started
        since then goes on recording."""
        session_id = next((session_id for session_id, recording in self.recordings.items()
                           if recording.talk_id == talk_id), None)
        if session_id is None:
            return None
        recording = self.recordings.pop(session_id)
        recording.close()
        return recording

    async def read(self, connection: Connection, track: MediaStreamTrack):
        """Reads the connection's audio track until it ends (the connection
        closed or was replaced), writing into the session's recording while
        it records. Started for every audio track the connection receives."""
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        try:
            # Until the track ends: aiortc ends it when the peer connection
            # closes, and recv() then raises MediaStreamError (below), also when
            # it ends while waiting. recv() waits for the next frame (about
            # every 20 ms), so the loop never spins. Stopping the live process
            # cancels the task.
            while track.readyState == "live":
                frame = await track.recv()
                now = timezone.now()
                recording = self.recordings.get(connection.session_id)
                if recording is None or recording.state != Recording.State.RECORDING:
                    continue
                for resampled in resampler.resample(frame):
                    # Packed s16 mono: the first plane, without its padding.
                    recording.write(bytes(resampled.planes[0])[:resampled.samples * BYTES_PER_SAMPLE], now)
                if now - recording.synced_at >= self.sync_interval:
                    # flush() is quick (to the OS); fsync waits for the disk,
                    # so it runs in a thread and the audio keeps coming.
                    try:
                        await asyncio.to_thread(os.fsync, recording.flush(now))
                    except (OSError, ValueError):
                        # Finished (closed) meanwhile: close() synced it already.
                        pass
        except MediaStreamError:
            # The track ended. The recording stays: a reconnect brings a new track.
            pass
        except Exception:
            logger.exception("Reading the audio of %s failed", connection)

    def close(self):
        """Closes every recording (the live process stops). The files stay, so
        the talks can be continued or saved after the restart."""
        for recording in self.recordings.values():
            recording.close()
        self.recordings.clear()
