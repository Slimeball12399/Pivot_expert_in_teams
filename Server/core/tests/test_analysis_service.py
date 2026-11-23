import io
import wave
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import File, FullVoiceResult, Session, Talk
from core.services.AnalysisService import analyse_talk
from core.services.FilesService import FilesService
from core.services.VoiceAnalysis import VoiceAnalysisError

# AnalysisService: the talk's stored audio fetched, converted to the WAV the
# tool reads, analysed, scored and saved, the talk COMPLETED. The tool itself is mocked here (it is tested in
# test_voice_analysis.py); the storage is Django's InMemoryStorage.

IN_MEMORY_STORAGES = {
    **settings.STORAGES,
    "files": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}


def wav_bytes(rate, seconds, channels=1):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x10\x00" * rate * seconds * channels)
    return buffer.getvalue()


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class AnalyseTalkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        trainer = make_trainer("anne@example.com")
        speaker = make_speaker("mikkel@example.com", trainer=trainer)
        cls.session = Session.objects.create(trainer=trainer, speaker=speaker.speaker_profile,
                                             status=Session.Status.FINISHED)

    def talk_with(self, content, content_type="audio/wav"):
        talk = Talk.objects.create(session=self.session, status=Talk.Status.PROCESSING, started_at=timezone.now())
        talk.audio = FilesService().create(SimpleUploadedFile("talk", content, content_type=content_type),
                                           File.Kind.AUDIO, content_type, self.session.id, talk.id)
        talk.save(update_fields=["audio"])
        return talk

    def test_converts_to_16_khz_mono_and_runs_the_long_analysis(self):
        # A browser-like recording: 48 kHz stereo, 2 s.
        talk = self.talk_with(wav_bytes(48000, 2, channels=2))
        seen = {}

        def long_analysis(wav_path, given_talk):
            with wave.open(str(wav_path), "rb") as wav:
                seen["format"] = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
                seen["seconds"] = wav.getnframes() / wav.getframerate()
            seen["talk"] = given_talk
            return FullVoiceResult(talk=given_talk, mean_f0=120.0)

        with mock.patch("core.services.AnalysisService.VoiceAnalysis") as tool:
            tool.return_value.get_long_analysis.side_effect = long_analysis
            result = analyse_talk(talk.id)

        self.assertEqual(seen["format"], (1, 2, 16000))
        self.assertAlmostEqual(seen["seconds"], 2.0, delta=0.05)
        self.assertEqual(seen["talk"], talk)
        with self.subTest("saved, the talk completed"):
            self.assertEqual(FullVoiceResult.objects.get(talk=talk).mean_f0, 120.0)
            self.assertEqual(result.talk, talk)
            talk.refresh_from_db()
            self.assertEqual(talk.status, Talk.Status.COMPLETED)

    def test_scored_and_an_earlier_attempt_replaced(self):
        talk = self.talk_with(wav_bytes(16000, 1))
        FullVoiceResult.objects.create(talk=talk, mean_f0=99.0)
        with mock.patch("core.services.AnalysisService.VoiceAnalysis") as tool:
            tool.return_value.get_long_analysis.side_effect = lambda path, t: FullVoiceResult(
                talk=t, mean_f1=525, mean_speaking_rate=4.0)
            analyse_talk(talk.id, sex="men")
        saved = FullVoiceResult.objects.get(talk=talk)  # one, the new one
        self.assertEqual(saved.mean_f1, 525)
        self.assertIsNotNone(saved.voice_score)

    def test_a_talk_no_longer_processing_is_left_alone(self):
        talk = self.talk_with(wav_bytes(16000, 1))
        Talk.objects.filter(pk=talk.pk).update(status=Talk.Status.DISCARDED)
        with mock.patch("core.services.AnalysisService.VoiceAnalysis") as tool:
            tool.return_value.get_long_analysis.side_effect = lambda path, t: FullVoiceResult(talk=t)
            self.assertIsNone(analyse_talk(talk.id))
        self.assertFalse(FullVoiceResult.objects.exists())

    def test_fails_clearly(self):
        with self.subTest("no stored audio"):
            talk = Talk.objects.create(session=self.session, status=Talk.Status.PROCESSING,
                                       started_at=timezone.now())
            with self.assertRaisesMessage(VoiceAnalysisError, "has no stored audio"):
                analyse_talk(talk.id)
        with self.subTest("audio that doesn't decode"):
            talk = self.talk_with(b"not audio", content_type="audio/webm")
            with self.assertRaisesMessage(VoiceAnalysisError, "can't be decoded"):
                analyse_talk(talk.id)
