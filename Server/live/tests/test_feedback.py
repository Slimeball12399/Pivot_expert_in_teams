import json
from datetime import timedelta
from unittest import mock

from asgiref.sync import async_to_sync
from django.utils import timezone

from core.models import PartialVoiceResult, Talk
from live.Services.AudioService import BYTES_PER_SAMPLE, SAMPLE_RATE
from live.Services.FeedbackService import FeedbackService

from .test_commands import CommandsServiceTestCase

# FeedbackService: the live voice windows of a talk being recorded. The voice
# analysis tool is mocked (it is tested in core/tests/test_voice_analysis.py);
# the scores come from ScoresService with the bands in core/voice_ranges.json.


def pcm(seconds):
    return b"\x00\x00" * int(SAMPLE_RATE * seconds)


class FeedbackServiceTests(CommandsServiceTestCase):
    def setUp(self):
        super().setUp()
        self.talk = Talk.objects.create(session=self.session, status=Talk.Status.RECORDING,
                                        started_at=timezone.now() - timedelta(seconds=40))
        self.recording = self.audio.start_recording(self.session.id, self.talk.id)
        self.connections = {self.connection.key: self.connection}
        self.feedback = FeedbackService(self.audio, self.connections, min_seconds=10)
        patcher = mock.patch("live.Services.FeedbackService.VoiceAnalysis")
        self.tool = patcher.start().return_value
        self.addCleanup(patcher.stop)
        self.tool.get_short_analysis.side_effect = lambda path, talk, start_at: PartialVoiceResult(
            talk=talk, start_at=start_at, window_length=timedelta(seconds=30),
            mean_speaking_rate=4.5, f0_range_q90_q10=40.0)

    def test_a_window_is_saved_and_sent(self):
        start_at = self.talk.started_at + timedelta(seconds=10)
        with self.assertLogs("live.Services.FeedbackService", "INFO"):
            async_to_sync(self.feedback.analyse)(self.session.id, self.talk.id, start_at, pcm(30))

        saved = PartialVoiceResult.objects.get(talk=self.talk)
        self.assertEqual(saved.start_at, start_at)
        self.assertIsNotNone(saved.voice_score)
        self.assertIsNotNone(saved.pace_score)
        self.assertIsNotNone(saved.pitch_variation_score)

        message = self.connection.channel.sent[-1]
        self.assertEqual(message["type"], "voice")
        self.assertEqual(message["talk_id"], str(self.talk.id))
        with self.subTest("when it was recorded, and where on the graph"):
            self.assertEqual(message["start_at"], start_at.isoformat())
            self.assertEqual(message["end_at"], (start_at + timedelta(seconds=30)).isoformat())
            self.assertEqual(message["t"], 40.0)  # its end, 40 s after the talk started
        with self.subTest("the scores and the raw values"):
            self.assertEqual(message["pace"], saved.pace_score)
            self.assertEqual(message["pitch"], saved.pitch_variation_score)
            self.assertEqual(message["speaking_rate"], 4.5)
            self.assertEqual(message["f0_range"], 40.0)

    def test_the_same_window_twice_is_saved_and_sent_once(self):
        start_at = self.talk.started_at
        with self.assertLogs("live.Services.FeedbackService", "INFO"):
            for _ in range(2):
                async_to_sync(self.feedback.analyse)(self.session.id, self.talk.id, start_at, pcm(30))
        self.assertEqual(PartialVoiceResult.objects.filter(talk=self.talk).count(), 1)
        self.assertEqual(len([m for m in self.connection.channel.sent if m.get("type") == "voice"]), 1)

    def test_a_failing_window_is_skipped(self):
        self.tool.get_short_analysis.side_effect = RuntimeError("tool crashed")
        with self.assertLogs("live.Services.FeedbackService", "WARNING"):
            async_to_sync(self.feedback.analyse)(self.session.id, self.talk.id, self.talk.started_at, pcm(30))
        self.assertFalse(PartialVoiceResult.objects.exists())
        self.assertEqual(self.connection.channel.sent, [])

    def test_the_wav_the_tool_gets(self):
        seen = {}

        def short_analysis(path, talk, start_at):
            import wave
            with wave.open(str(path), "rb") as wav:
                seen["format"] = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
                seen["seconds"] = wav.getnframes() / wav.getframerate()
            seen["path"] = path
            return PartialVoiceResult(talk=talk, start_at=start_at, window_length=timedelta(seconds=12))

        self.tool.get_short_analysis.side_effect = short_analysis
        self.feedback.analyse_window(self.talk.id, self.talk.started_at, pcm(12))
        self.assertEqual(seen["format"], (1, BYTES_PER_SAMPLE, SAMPLE_RATE))
        self.assertEqual(seen["seconds"], 12)
        self.assertFalse(seen["path"].exists())  # deleted after

    def test_tick_only_analyses_long_enough_recording_windows(self):
        with mock.patch.object(self.feedback, "analyse", new=mock.MagicMock()) as analyse, \
                mock.patch("live.Services.FeedbackService.asyncio.create_task") as create_task, \
                self.assertLogs("live.Services.FeedbackService", "INFO"):
            with self.subTest("too short: nothing"):
                self.recording.write(pcm(5), timezone.now())
                self.feedback.tick()
                create_task.assert_not_called()
            with self.subTest("long enough: analysed"):
                self.recording.write(pcm(6), timezone.now())
                self.feedback.tick()
                create_task.assert_called_once()
                session_id, talk_id, _, window = analyse.call_args.args
                self.assertEqual((session_id, talk_id), (self.session.id, self.talk.id))
                self.assertEqual(len(window), len(pcm(11)))
            with self.subTest("one still running: skipped"):
                self.feedback.tick()
                create_task.assert_called_once()
            with self.subTest("paused: nothing"):
                self.feedback.running.clear()
                self.recording.pause()
                self.feedback.tick()
                create_task.assert_called_once()
