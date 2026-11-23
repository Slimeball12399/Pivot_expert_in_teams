from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import FullVoiceResult, Session, Talk
from live.client import LIVE_UNAVAILABLE, LiveError

# GET /talks/<id>/: one talk's graphs as JSON, for the session page's talks
# card; POST /talks/<id>/finish/: End talk on the live screen. The HTTP layer only: what get_talk_graphs() returns is tested in
# core/tests/test_graphs_service.py, get_talk() in core/tests/test_talk_crud.py.


class TalkGraphsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)
        now = timezone.now()
        session = Session.objects.create(
            trainer=cls.trainer, speaker=cls.speaker.speaker_profile, status=Session.Status.FINISHED,
            started_at=now - timedelta(hours=1), ended_at=now - timedelta(minutes=50))
        cls.talk = Talk.objects.create(
            session=session, status=Talk.Status.COMPLETED,
            started_at=now - timedelta(minutes=58), duration=timedelta(seconds=40))
        FullVoiceResult.objects.create(talk=cls.talk, voice_score=72.6)
        cls.url = reverse("web:talk", args=[cls.talk.id])

    def test_returns_the_graphs_as_json(self):
        self.assertEqual(self.url, f"/talks/{self.talk.id}/")
        self.client.force_login(self.trainer.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            set(data), {"talk", "voice_config", "stability_config", "speech_score", "stability_score"})
        self.assertEqual(data["talk"]["id"], str(self.talk.id))
        self.assertEqual(data["talk"]["number"], 1)
        self.assertEqual(data["speech_score"], 73)

    def test_rejects(self):
        with self.subTest("logged out: redirected to the login page"):
            response = self.client.get(self.url)
            self.assertRedirects(
                response, f"{reverse(settings.LOGIN_URL)}?next={self.url}", fetch_redirect_response=False)

        with self.subTest("a speaker: not allowed"):
            self.client.force_login(self.speaker)
            self.assertEqual(self.client.get(self.url).status_code, 403)

        with self.subTest("another trainer's talk: not found"):
            self.client.force_login(make_trainer("bo@example.com").user)
            self.assertEqual(self.client.get(self.url).status_code, 404)

        with self.subTest("a talk that doesn't exist: not found"):
            self.client.force_login(self.trainer.user)
            missing = reverse("web:talk", args=["00000000-0000-0000-0000-000000000000"])
            self.assertEqual(self.client.get(missing).status_code, 404)

        with self.subTest("only GET"):
            self.assertEqual(self.client.post(self.url).status_code, 405)


class TalkFinishViewTests(TestCase):
    """POST /talks/<id>/finish/: End talk. finish_talk's rules are in
    core/tests/test_talk_crud.py; the live process is mocked (LiveClient)."""

    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        cls.speaker = make_speaker("mikkel@example.com", trainer=cls.trainer)
        cls.session = Session.objects.create(
            trainer=cls.trainer, speaker=cls.speaker.speaker_profile, status=Session.Status.LIVE,
            started_at=timezone.now() - timedelta(minutes=5))

    def setUp(self):
        self.client.force_login(self.trainer.user)
        patcher = mock.patch("web.views.talks.LiveClient")
        self.live_client = patcher.start().return_value
        self.addCleanup(patcher.stop)
        # Nothing recorded by default (the real one gives the PCM's path).
        self.live_client.stop_recording.return_value = None
        self.talk = Talk.objects.create(session=self.session, status=Talk.Status.RECORDING,
                                        started_at=timezone.now() - timedelta(seconds=30))
        self.url = reverse("web:talk_finish", args=[self.talk.id])

    def test_finishes_it_and_stops_its_recording(self):
        self.assertEqual(self.url, f"/talks/{self.talk.id}/finish/")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": str(self.talk.id)})
        self.talk.refresh_from_db()
        self.assertEqual(self.talk.status, Talk.Status.PROCESSING)
        self.live_client.stop_recording.assert_called_once_with(self.talk.id)

    def test_the_recording_stops_before_the_talk_is_finished(self):
        # finish_talk will upload the recording, so it must be closed by then.
        seen = []
        self.live_client.stop_recording.side_effect = lambda talk_id: seen.append(
            Talk.objects.get(pk=talk_id).status)
        self.client.post(self.url)
        self.assertEqual(seen, [Talk.Status.RECORDING])

    def test_finished_even_when_the_live_process_cant_say_so(self):
        cases = [("nothing recording it", LiveError("not_recording", "Not recording.", 404)),
                 ("not reachable", LiveError(LIVE_UNAVAILABLE, "Can't be reached."))]
        for label, error in cases:
            with self.subTest(label):
                # One talk going on at a time: the one before is done.
                Talk.objects.filter(session=self.session).update(status=Talk.Status.COMPLETED)
                talk = Talk.objects.create(session=self.session, status=Talk.Status.RECORDING,
                                           started_at=timezone.now())
                self.live_client.stop_recording.side_effect = error
                if error.status is None:
                    # Unreachable: logged, so the test checks the log and keeps the output clean.
                    with self.assertLogs("web.views.talks", "WARNING"):
                        response = self.client.post(reverse("web:talk_finish", args=[talk.id]))
                else:
                    response = self.client.post(reverse("web:talk_finish", args=[talk.id]))
                self.assertEqual(response.status_code, 200)
                talk.refresh_from_db()
                self.assertEqual(talk.status, Talk.Status.PROCESSING)

    def test_the_browsers_recording_and_the_live_processs_go_to_finish_talk(self):
        self.live_client.stop_recording.return_value = Path("/files/recordings/x.pcm")
        audio = SimpleUploadedFile("talk.webm", b"webm", content_type="audio/webm")
        seen = {}

        def finishing(**kwargs):
            # Read during the call: Django closes the upload once the request is done.
            seen.update(kwargs, content=kwargs["audio"].read())
            return self.talk

        with mock.patch("web.views.talks.finish_talk", side_effect=finishing):
            response = self.client.post(self.url, {"audio": audio})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(seen["content"], b"webm")
        self.assertEqual(seen["recording"], Path("/files/recordings/x.pcm"))

    def test_a_file_that_isnt_audio_we_take(self):
        for label, audio in [("not audio", SimpleUploadedFile("talk.txt", b"hi", content_type="text/plain")),
                             ("empty", SimpleUploadedFile("talk.webm", b"", content_type="audio/webm"))]:
            with self.subTest(label):
                response = self.client.post(self.url, {"audio": audio})
                self.assertEqual(response.status_code, 400)
                self.assertIn("audio", response.json()["errors"])
        # Refused before anything changes.
        self.live_client.stop_recording.assert_not_called()
        self.talk.refresh_from_db()
        self.assertEqual(self.talk.status, Talk.Status.RECORDING)

    def test_rejects(self):
        with self.subTest("not going on: 409, the live process isn't asked"):
            Talk.objects.filter(pk=self.talk.pk).update(status=Talk.Status.COMPLETED)
            self.assertEqual(self.client.post(self.url).status_code, 409)
            self.live_client.stop_recording.assert_not_called()
        with self.subTest("someone else's: 404"):
            self.client.force_login(make_trainer("bo@example.com").user)
            self.assertEqual(self.client.post(self.url).status_code, 404)
        with self.subTest("a speaker: not allowed"):
            self.client.force_login(self.speaker)
            self.assertEqual(self.client.post(self.url).status_code, 403)
        with self.subTest("only POST"):
            self.client.force_login(self.trainer.user)
            self.assertEqual(self.client.get(self.url).status_code, 405)
