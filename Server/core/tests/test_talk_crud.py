import uuid
from unittest import mock
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import File, FullVoiceResult, PartialVoiceResult, Session, Talk
from core.services.FilesService import FilesService
from core.services.SessionsService import INVALID_TRANSITION, NOT_ADMIN, SESSION_NOT_YOURS
from core.services.TalksService import (
    SESSION_NOT_LIVE,
    TALK_ALREADY_OPEN,
    TALK_NOT_YOURS,
    discard_talk,
    finish_talk,
    get_talk,
    pause_talk,
    resume_talk,
    start_talk,
)

# The rules of TalksService: the talk state machine (start, pause, resume,
# finish, discard), that only the session's trainer controls talks, and the
# pause bookkeeping behind a talk's duration, and reading talks with their
# voice results.
# Storing the audio itself is tested in test_files_service.py.

IN_MEMORY_STORAGES = {
    **settings.STORAGES,
    "files": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}


class TalkServiceTestCase(TestCase):
    """Shared data and helpers for the talk tests below."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", cls.trainer).speaker_profile
        # A second speaker of Anne's, for a second live session (one live session per speaker).
        cls.second_speaker = make_speaker("sofie@example.com", cls.trainer).speaker_profile
        cls.other_trainer = make_trainer("bo@example.com")

    def setUp(self):
        self.live = self.make_session()

    def make_session(self, status=Session.Status.LIVE, *, speaker=None):
        """One of Anne's sessions, made straight in the database."""
        return Session.objects.create(
            trainer=self.trainer, speaker=speaker or self.speaker, status=status,
            started_at=timezone.now() if status == Session.Status.LIVE else None)

    def make_talk(self, status=Talk.Status.RECORDING, *, session=None, minutes_ago=10):
        """A talk started `minutes_ago` minutes ago, by default in self.live.
        A session holds one recording or paused talk at a time."""
        return Talk.objects.create(
            session=session or self.live, status=status,
            started_at=timezone.now() - timedelta(minutes=minutes_ago))

    def assertRaisesCode(self, code, func, **kwargs):
        with self.assertRaises(ValidationError) as ctx:
            func(**kwargs)
        self.assertEqual(ctx.exception.code, code)


class StartTalkTests(TalkServiceTestCase):
    def test_starts_a_recording_talk(self):
        talk = start_talk(trainer=self.trainer.user, session_id=self.live.pk)

        self.assertEqual(talk.session, self.live)
        self.assertEqual(talk.status, Talk.Status.RECORDING)
        self.assertIsNotNone(talk.started_at)
        self.assertIsNone(talk.duration)

    def test_rejects(self):
        live = self.live
        waiting = self.make_session(Session.Status.NOT_STARTED)
        cases = [
            ("a speaker", NOT_ADMIN, self.speaker.user, live.pk),
            ("another trainer", SESSION_NOT_YOURS, self.other_trainer.user, live.pk),
            ("a session that doesn't exist", SESSION_NOT_YOURS, self.trainer.user, uuid.uuid4()),
            ("a session that isn't live", SESSION_NOT_LIVE, self.trainer.user, waiting.pk),
        ]
        for label, code, user, session_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, start_talk, trainer=user, session_id=session_id)

        self.assertFalse(Talk.objects.exists())

    def test_one_talk_at_a_time(self):
        session = self.live
        talk = self.make_talk()

        for status in (Talk.Status.RECORDING, Talk.Status.PAUSED):
            with self.subTest(f"refused while one is {status.lower()}"):
                Talk.objects.filter(pk=talk.pk).update(status=status)
                self.assertRaisesCode(TALK_ALREADY_OPEN, start_talk,
                                      trainer=self.trainer.user, session_id=session.pk)

        with self.subTest("allowed once the open one is finished"):
            Talk.objects.filter(pk=talk.pk).update(status=Talk.Status.PROCESSING)
            start_talk(trainer=self.trainer.user, session_id=session.pk)
            self.assertEqual(session.talks.count(), 2)


class PauseAndResumeTalkTests(TalkServiceTestCase):
    def test_pause_and_resume(self):
        talk = self.make_talk()

        with self.subTest("pause: paused, with a pause going on"):
            paused = pause_talk(trainer=self.trainer.user, talk_id=talk.pk)
            self.assertEqual(paused.status, Talk.Status.PAUSED)
            self.assertEqual(talk.pauses.filter(resumed_at__isnull=True).count(), 1)

        with self.subTest("resume: recording again, and the pause is closed"):
            resumed = resume_talk(trainer=self.trainer.user, talk_id=talk.pk)
            self.assertEqual(resumed.status, Talk.Status.RECORDING)
            self.assertFalse(talk.pauses.filter(resumed_at__isnull=True).exists())

        with self.subTest("a second pause is its own row"):
            pause_talk(trainer=self.trainer.user, talk_id=talk.pk)
            self.assertEqual(talk.pauses.count(), 2)

    def test_rejects(self):
        recording = self.make_talk()
        paused = self.make_talk(
            Talk.Status.PAUSED, session=self.make_session(speaker=self.second_speaker))
        cases = [
            ("pause, as a speaker", pause_talk, NOT_ADMIN, self.speaker.user, recording.pk),
            ("pause, as another trainer", pause_talk, TALK_NOT_YOURS, self.other_trainer.user, recording.pk),
            ("pause, a talk that doesn't exist", pause_talk, TALK_NOT_YOURS, self.trainer.user, uuid.uuid4()),
            ("pause, a talk that is already paused", pause_talk, INVALID_TRANSITION, self.trainer.user, paused.pk),
            ("resume, as a speaker", resume_talk, NOT_ADMIN, self.speaker.user, paused.pk),
            ("resume, as another trainer", resume_talk, TALK_NOT_YOURS, self.other_trainer.user, paused.pk),
            ("resume, a talk that isn't paused", resume_talk, INVALID_TRANSITION, self.trainer.user, recording.pk),
        ]
        for label, func, code, user, talk_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, func, trainer=user, talk_id=talk_id)

        recording.refresh_from_db()
        paused.refresh_from_db()
        self.assertEqual(recording.status, Talk.Status.RECORDING)
        self.assertEqual(paused.status, Talk.Status.PAUSED)


class FinishTalkTests(TalkServiceTestCase):
    @override_settings(STORAGES=IN_MEMORY_STORAGES)
    def test_stores_the_browsers_recording(self):
        talk = self.make_talk()
        audio = SimpleUploadedFile("talk.webm", b"webm bytes", content_type="audio/webm")
        # Not real WebM, and no PCM: stored as the only copy, with a warning.
        with self.assertLogs("core.services.TalksService", "WARNING"):
            finished = finish_talk(trainer=self.trainer.user, talk_id=talk.pk, audio=audio)
        talk.refresh_from_db()
        self.assertEqual(finished.status, Talk.Status.PROCESSING)
        self.assertEqual(talk.audio.content_type, "audio/webm")
        self.assertTrue(talk.audio.key.endswith(".webm"))
        with FilesService().open(talk.audio) as stored:
            self.assertEqual(stored.read(), b"webm bytes")

    def pcm_file(self, seconds=1):
        """A PCM file as the live process writes it: 16 kHz mono 16-bit."""
        import tempfile

        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        pcm = Path(folder.name) / "talk.pcm"
        pcm.write_bytes(b"\x01\x00" * 16000 * seconds)
        return pcm

    def wav_upload(self, seconds):
        """A WAV the way a browser file comes in: decodable audio, `seconds` long."""
        import io
        import wave

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * 16000 * seconds)
        return SimpleUploadedFile("talk.wav", buffer.getvalue(), content_type="audio/wav")

    def talk_of(self, seconds):
        """A talk going on for `seconds` seconds."""
        return Talk.objects.create(session=self.live, status=Talk.Status.RECORDING,
                                   started_at=timezone.now() - timedelta(seconds=seconds))

    @override_settings(STORAGES=IN_MEMORY_STORAGES)
    def test_else_stores_the_live_processs_recording_as_wav(self):
        import wave

        pcm = self.pcm_file()
        talk = self.make_talk()
        with self.captureOnCommitCallbacks(execute=True):
            finish_talk(trainer=self.trainer.user, talk_id=talk.pk, recording=pcm)
        talk.refresh_from_db()
        self.assertEqual(talk.audio.content_type, "audio/wav")
        with FilesService().open(talk.audio) as stored, wave.open(stored, "rb") as wav:
            self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (1, 2, 16000))
            self.assertEqual(wav.readframes(wav.getnframes()), b"\x01\x00" * 16000)
        with self.subTest("stored: the PCM is deleted after the commit"):
            self.assertFalse(pcm.exists())

    @override_settings(STORAGES=IN_MEMORY_STORAGES)
    def test_an_intact_browser_recording_is_stored_and_the_pcm_deleted(self):
        pcm = self.pcm_file()
        talk = self.talk_of(seconds=3)
        with self.captureOnCommitCallbacks(execute=True):
            finish_talk(trainer=self.trainer.user, talk_id=talk.pk, audio=self.wav_upload(seconds=3), recording=pcm)
        talk.refresh_from_db()
        with FilesService().open(talk.audio) as stored:
            # The browser's file (silence), not the PCM's samples.
            self.assertIn(b"\x00\x00" * 100, stored.read())
        self.assertFalse(pcm.exists())

    @override_settings(STORAGES=IN_MEMORY_STORAGES)
    def test_a_broken_or_short_browser_recording_gives_way_to_the_pcm(self):
        cases = [
            ("doesn't decode", lambda: SimpleUploadedFile("talk.webm", b"not webm", content_type="audio/webm"), 3),
            ("much shorter than the talk", lambda: self.wav_upload(seconds=1), 60),
        ]
        for label, upload, talk_seconds in cases:
            with self.subTest(label):
                Talk.objects.filter(session=self.live).update(status=Talk.Status.COMPLETED)
                pcm = self.pcm_file()
                talk = self.talk_of(seconds=talk_seconds)
                with self.assertLogs("core.services.TalksService", "WARNING"), \
                        self.captureOnCommitCallbacks(execute=True):
                    finish_talk(trainer=self.trainer.user, talk_id=talk.pk, audio=upload(), recording=pcm)
                talk.refresh_from_db()
                with FilesService().open(talk.audio) as stored:
                    self.assertIn(b"\x01\x00" * 100, stored.read())  # the PCM's samples
                self.assertFalse(pcm.exists())

    @override_settings(STORAGES=IN_MEMORY_STORAGES)
    def test_the_analysis_is_enqueued_after_the_commit(self):
        talk = self.talk_of(seconds=3)
        with mock.patch("core.services.TalksService.analyse_talk") as task:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                finish_talk(trainer=self.trainer.user, talk_id=talk.pk, audio=self.wav_upload(seconds=3))
            task.enqueue.assert_not_called()  # not before the commit
            for callback in callbacks:
                callback()
        task.enqueue.assert_called_once_with(str(talk.id))

    def test_no_audio_no_analysis(self):
        talk = self.talk_of(seconds=3)
        with mock.patch("core.services.TalksService.analyse_talk") as task, \
                self.captureOnCommitCallbacks(execute=True):
            finish_talk(trainer=self.trainer.user, talk_id=talk.pk)
        task.enqueue.assert_not_called()

    @override_settings(STORAGES=IN_MEMORY_STORAGES)
    def test_without_a_confirmed_recording_nothing_is_deleted(self):
        # The live process didn't confirm it closed the file: no path comes in.
        pcm = self.pcm_file()
        talk = self.talk_of(seconds=3)
        with self.captureOnCommitCallbacks(execute=True):
            finish_talk(trainer=self.trainer.user, talk_id=talk.pk, audio=self.wav_upload(seconds=3))
        self.assertTrue(pcm.exists())

    @override_settings(STORAGES=IN_MEMORY_STORAGES)
    def test_the_browsers_recording_wins_and_nothing_means_no_audio(self):
        with self.subTest("a broken browser file and no PCM: the browser's, the only copy"):
            talk = self.make_talk()
            audio = SimpleUploadedFile("talk.ogg", b"ogg", content_type="audio/ogg")
            with self.assertLogs("core.services.TalksService", "WARNING"):
                finish_talk(trainer=self.trainer.user, talk_id=talk.pk, audio=audio,
                            recording=Path("/nowhere/talk.pcm"))
            talk.refresh_from_db()
            self.assertEqual(talk.audio.content_type, "audio/ogg")
        with self.subTest("neither, or a PCM that isn't there: no audio"):
            talk = self.make_talk()
            finish_talk(trainer=self.trainer.user, talk_id=talk.pk, recording=Path("/nowhere/talk.pcm"))
            talk.refresh_from_db()
            self.assertIsNone(talk.audio)

    def test_duration_leaves_out_the_pauses(self):
        with self.subTest("recording: the whole time since the start"):
            talk = self.make_talk(minutes_ago=10)
            finished = finish_talk(trainer=self.trainer.user, talk_id=talk.pk)
            self.assertEqual(finished.status, Talk.Status.PROCESSING)
            self.assertAlmostEqual(finished.duration.total_seconds(), 10 * 60, delta=5)

        with self.subTest("paused: a 2 minute pause and the 1 minute one going on are left out"):
            talk = self.make_talk(Talk.Status.PAUSED, minutes_ago=10)
            now = timezone.now()
            talk.pauses.create(paused_at=now - timedelta(minutes=6), resumed_at=now - timedelta(minutes=4))
            talk.pauses.create(paused_at=now - timedelta(minutes=1))

            finished = finish_talk(trainer=self.trainer.user, talk_id=talk.pk)

            self.assertEqual(finished.status, Talk.Status.PROCESSING)
            self.assertAlmostEqual(finished.duration.total_seconds(), 7 * 60, delta=5)
            self.assertFalse(talk.pauses.filter(resumed_at__isnull=True).exists())

    def test_rejects(self):
        recording = self.make_talk()
        processing = self.make_talk(Talk.Status.PROCESSING)
        cases = [
            ("a speaker", NOT_ADMIN, self.speaker.user, recording.pk),
            ("another trainer", TALK_NOT_YOURS, self.other_trainer.user, recording.pk),
            ("a talk that is already finished", INVALID_TRANSITION, self.trainer.user, processing.pk),
        ]
        for label, code, user, talk_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, finish_talk, trainer=user, talk_id=talk_id)

        recording.refresh_from_db()
        self.assertEqual(recording.status, Talk.Status.RECORDING)
        self.assertIsNone(recording.duration)


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class DiscardTalkTests(TalkServiceTestCase):
    def test_discards_and_deletes_the_audio(self):
        talk = self.make_talk(Talk.Status.COMPLETED)
        files = FilesService()
        audio = files.create(
            SimpleUploadedFile("talk.wav", b"RIFF fake wav bytes", content_type="audio/wav"),
            kind=File.Kind.AUDIO, content_type="audio/wav",
            session_id=talk.session_id, talk_id=talk.pk)
        Talk.objects.filter(pk=talk.pk).update(audio=audio)

        # The audio is deleted after the commit, so run the on_commit callbacks.
        with self.captureOnCommitCallbacks(execute=True):
            discarded = discard_talk(trainer=self.trainer.user, talk_id=talk.pk)

        self.assertEqual(discarded.status, Talk.Status.DISCARDED)
        self.assertFalse(File.objects.filter(pk=audio.pk).exists())
        self.assertFalse(files.storage.exists(audio.key))
        talk.refresh_from_db()
        self.assertIsNone(talk.audio)

    def test_discarding_an_open_talk_closes_it(self):
        talk = self.make_talk(Talk.Status.PAUSED)
        talk.pauses.create(paused_at=timezone.now() - timedelta(minutes=1))

        discard_talk(trainer=self.trainer.user, talk_id=talk.pk)

        with self.subTest("its pause is closed"):
            self.assertFalse(talk.pauses.filter(resumed_at__isnull=True).exists())
        with self.subTest("a new talk can start"):
            start_talk(trainer=self.trainer.user, session_id=talk.session_id)

    def test_rejects(self):
        recording = self.make_talk()
        discarded = self.make_talk(Talk.Status.DISCARDED)
        cases = [
            ("a speaker", NOT_ADMIN, self.speaker.user, recording.pk),
            ("another trainer", TALK_NOT_YOURS, self.other_trainer.user, recording.pk),
            ("a talk that is already discarded", INVALID_TRANSITION, self.trainer.user, discarded.pk),
        ]
        for label, code, user, talk_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(code, discard_talk, trainer=user, talk_id=talk_id)

        recording.refresh_from_db()
        self.assertEqual(recording.status, Talk.Status.RECORDING)


class GetTalkTests(TalkServiceTestCase):
    def test_gets_the_talk_with_its_results_in_time_order(self):
        talk = self.make_talk(Talk.Status.COMPLETED)
        FullVoiceResult.objects.create(talk=talk, voice_score=6.0)
        # Saved out of order, read back in time order.
        for seconds in (10, 0, 5):
            PartialVoiceResult.objects.create(
                talk=talk, start_at=talk.started_at + timedelta(seconds=seconds),
                window_length=timedelta(seconds=30))

        for label, user in [("the trainer", self.trainer.user), ("the speaker", self.speaker.user)]:
            with self.subTest(label):
                found = get_talk(user=user, talk_id=talk.pk)

                with self.assertNumQueries(0):
                    self.assertEqual(found.full_voice_result.voice_score, 6.0)
                    starts = [p.start_at - talk.started_at
                              for p in found.partial_voice_results.all()]
                self.assertEqual(starts, [timedelta(seconds=s) for s in (0, 5, 10)])

    def test_a_talk_without_results(self):
        found = get_talk(user=self.trainer.user, talk_id=self.make_talk().pk)

        self.assertIsNone(getattr(found, "full_voice_result", None))
        self.assertEqual(list(found.partial_voice_results.all()), [])

    def test_rejects(self):
        talk = self.make_talk()
        cases = [
            ("another trainer", self.other_trainer.user, talk.pk),
            ("another speaker", self.second_speaker.user, talk.pk),
            ("a talk that doesn't exist", self.trainer.user, uuid.uuid4()),
        ]
        for label, user, talk_id in cases:
            with self.subTest(label):
                self.assertRaisesCode(TALK_NOT_YOURS, get_talk, user=user, talk_id=talk_id)
