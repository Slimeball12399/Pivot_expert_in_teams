from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.utils import make_speaker, make_trainer
from core.models import FullVoiceResult, Session, Talk

# GET /talks/<id>/: one talk's graphs as JSON, for the session page's talks
# card. The HTTP layer only: what get_talk_graphs() returns is tested in
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
