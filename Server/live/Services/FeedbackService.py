"""The live voice feedback while a talk is recorded: every interval seconds
(5), for each talk recording, the last window of its audio (up to 30 s, the
recording's rolling window, AudioService) is analysed, scored, saved as a
PartialVoiceResult and sent to the trainer's browser on the "control"
channel, for the live voice graph:

  {"type": "voice", "talk_id", "start_at", "end_at",   (UTC, ISO 8601: when the
                                                         window was recorded)
   "t",                                                 (seconds from the talk's
                                                         start to the window's end,
                                                         pauses included: the
                                                         graph's x)
   "voice_score",                                       (0 to 100)
   "pace", "pitch",                                     (-10 to +10: pace_score,
                                                         pitch_variation_score)
   "speaking_rate", "f0_range"}                         (the raw values: syllables/s, Hz)

A window is analysed once at least min_seconds (10) have been recorded since
the talk started or resumed; before it is 30 s long it is simply shorter (its
window_length). At most one analysis per talk at a time: a tick that finds the
last one still running skips that talk. The voice analysis tool waits on a
process of its own, so it runs in a thread (asyncio.to_thread), never on the
event loop the audio and the connections run on; the database work goes
through sync_to_async.

A window that fails (the tool, a short or silent window) is logged and
skipped: the next one comes interval seconds later. Nothing is retried.
"""
import asyncio
import json
import logging
import tempfile
import time
import uuid
import wave
from datetime import datetime
from pathlib import Path

from asgiref.sync import sync_to_async
from django.db import IntegrityError, transaction

from core.models import PartialVoiceResult, Talk
from core.services.ScoresService import score_result, signed_score
from core.services.VoiceAnalysis import VoiceAnalysis
from live.models import Connection, Recording
from live.Services.AudioService import BYTES_PER_SAMPLE, SAMPLE_RATE, AudioService

logger = logging.getLogger(__name__)


class FeedbackService:
    """The live voice windows of every talk being recorded."""

    def __init__(self, audio: AudioService, connections: dict, interval: float = 5,
                 min_seconds: float = 10, sex: str | None = "men"):
        # The recordings, with their rolling windows.
        self.audio = audio
        # ConnectionService.connections: where the trainer's channel is, by (session id, kind).
        self.connections = connections
        # Seconds between two windows of the same talk.
        self.interval = interval
        # Seconds a window needs before it is analysed.
        self.min_seconds = min_seconds
        # The bands for the measures that have them per sex (ScoresService):
        # every speaker as a man until the speaker's sex is stored.
        self.sex = sex
        # The analysis running for each session, if one is.
        self.running: dict[uuid.UUID, asyncio.Task] = {}
        # Each talk's start (UTC), for the windows' t; read once per talk.
        self.started_at: dict[uuid.UUID, datetime] = {}
        self.loop_task: asyncio.Task | None = None

    def start(self):
        """Starts the ticking (the live process's startup)."""
        self.loop_task = asyncio.create_task(self.run())
        logger.info("Live voice feedback on: a window every %s s, from %s s recorded",
                    self.interval, self.min_seconds)

    async def close(self):
        """Stops the ticking and the analyses running (the live process stops)."""
        tasks = [task for task in [self.loop_task, *self.running.values()] if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.running.clear()

    async def run(self):
        """Every interval seconds: a window for each talk recording."""
        while True:
            await asyncio.sleep(self.interval)
            self.tick()

    def tick(self):
        """Starts the analysis of the current window of each talk recording,
        unless its last one is still running or the window is too short."""
        for session_id, recording in list(self.audio.recordings.items()):
            if recording.state != Recording.State.RECORDING or session_id in self.running:
                continue
            window = recording.current_window()
            if window is None or len(window[1]) < self.min_seconds * SAMPLE_RATE * BYTES_PER_SAMPLE:
                continue
            start_at, pcm = window
            logger.info("Live voice window of talk %s: analysing %.1f s",
                        recording.talk_id, len(pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE))
            task = asyncio.create_task(self.analyse(session_id, recording.talk_id, start_at, pcm))
            self.running[session_id] = task
            task.add_done_callback(lambda _, session_id=session_id: self.running.pop(session_id, None))

    async def analyse(self, session_id: uuid.UUID, talk_id: uuid.UUID, start_at: datetime, pcm: bytes):
        """One window: analysed and scored in a thread, saved, sent."""
        began = time.monotonic()
        try:
            if talk_id not in self.started_at:
                self.started_at[talk_id] = await Talk.objects.values_list("started_at", flat=True).aget(pk=talk_id)
            result = await asyncio.to_thread(self.analyse_window, talk_id, start_at, pcm)

            def save():
                # Its own savepoint: a duplicate window fails alone, not a
                # transaction around it.
                with transaction.atomic():
                    result.save()

            await sync_to_async(save)()
        except IntegrityError:
            # The same window again (no new audio since the last tick).
            return
        except Exception as error:
            logger.warning("Live voice window of talk %s at %s skipped: %s", talk_id, start_at, error)
            return

        connection = self.connections.get((session_id, Connection.Kind.TRAINER_AUDIO))
        if connection is None or connection.channel.readyState != "open":
            logger.info("Live voice window of talk %s saved, not sent: no open channel", talk_id)
            return
        end_at = result.start_at + result.window_length
        connection.channel.send(json.dumps({
            "type": "voice",
            "talk_id": str(talk_id),
            "start_at": result.start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "t": round((end_at - self.started_at[talk_id]).total_seconds(), 1),
            "voice_score": result.voice_score,
            "pace": result.pace_score,
            "pitch": result.pitch_variation_score,
            "speaking_rate": result.mean_speaking_rate,
            "f0_range": result.f0_range_q90_q10,
        }))
        logger.info("Live voice window of talk %s sent after %.1f s: score %s, pace %s, pitch %s",
                    talk_id, time.monotonic() - began,
                    None if result.voice_score is None else round(result.voice_score),
                    None if result.pace_score is None else round(result.pace_score, 1),
                    None if result.pitch_variation_score is None else round(result.pitch_variation_score, 1))

    def analyse_window(self, talk_id: uuid.UUID, start_at: datetime, pcm: bytes) -> PartialVoiceResult:
        """The window's PCM as a WAV in a temporary folder (deleted after),
        through the voice analysis tool, scored: an unsaved PartialVoiceResult.
        Runs in a thread: it waits on the tool's process."""
        with tempfile.TemporaryDirectory() as work:
            wav_path = Path(work) / f"{talk_id}.wav"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(BYTES_PER_SAMPLE)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes(pcm)
            # Talk(pk=...): the window only needs the talk's id.
            result = VoiceAnalysis().get_short_analysis(wav_path, Talk(pk=talk_id), start_at)
        result.voice_score = score_result(result, sex=self.sex)["voice_score"]
        result.pace_score = signed_score("mean_speaking_rate", result.mean_speaking_rate, self.sex, partial=True)
        result.pitch_variation_score = signed_score("f0_range_q90_q10", result.f0_range_q90_q10, self.sex,
                                                    partial=True)
        return result
