import uuid
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.tests.utils import make_speaker, make_trainer
from core.models import FullVoiceResult, PartialVoiceResult, Session, Talk


class TalkEndpointTests(APITestCase):
    """The HTTP layer. The rules are tested in core/tests/test_talk_crud.py."""

    def setUp(self):
        self.trainer = make_trainer("anne@example.com")
        self.speaker = make_speaker("mikkel@example.com", self.trainer)
        session = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile,
            status=Session.Status.FINISHED)
        self.talk = Talk.objects.create(
            session=session, status=Talk.Status.COMPLETED,
            started_at=timezone.now() - timedelta(minutes=10), duration=timedelta(minutes=4))
        self.url = reverse("api:talk", args=[self.talk.pk])

    def test_a_talk_in_full(self):
        FullVoiceResult.objects.create(talk=self.talk, voice_score=72.5, spl_dbfs=-24.0)
        # Saved out of order, returned in time order.
        for seconds, pace in [(5, 1.5), (0, -2.0)]:
            PartialVoiceResult.objects.create(
                talk=self.talk, start_at=self.talk.started_at + timedelta(seconds=seconds),
                window_length=timedelta(seconds=30), voice_score=3.0,
                pace_score=pace, pitch_variation_score=0.5)

        for label, user in [("the trainer", self.trainer.user), ("the speaker", self.speaker)]:
            with self.subTest(label):
                self.client.force_authenticate(user)
                response = self.client.get(self.url)

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
                body = response.json()
                self.assertEqual(body["id"], str(self.talk.pk))
                self.assertEqual(body["full_voice_result"]["voice_score"], 72.5)
                self.assertEqual(body["full_voice_result"]["spl_dbfs"], -24.0)
                windows = body["partial_voice_results"]
                self.assertEqual([w["pace_score"] for w in windows], [-2.0, 1.5])
                self.assertEqual(set(windows[0]), {
                    "start_at", "voice_score", "pace_score", "pitch_variation_score"})

    def test_a_talk_without_results(self):
        self.client.force_authenticate(self.trainer.user)
        body = self.client.get(self.url).json()

        self.assertIsNone(body["full_voice_result"])
        self.assertIsNone(body["voice_score"])
        self.assertEqual(body["partial_voice_results"], [])

    def test_not_found(self):
        cases = [
            ("not logged in", None, self.url, status.HTTP_401_UNAUTHORIZED),
            ("another trainer", make_trainer("bo@example.com").user, self.url,
             status.HTTP_404_NOT_FOUND),
            ("a talk that doesn't exist", self.trainer.user,
             reverse("api:talk", args=[uuid.uuid4()]), status.HTTP_404_NOT_FOUND),
        ]
        for label, user, url, expected in cases:
            with self.subTest(label):
                self.client.force_authenticate(user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, expected)
                if expected == status.HTTP_404_NOT_FOUND:
                    self.assertEqual(response.json()["code"], "talk_not_yours")

    def test_delete_discards(self):
        with self.subTest("a speaker: 403"):
            self.client.force_authenticate(self.speaker)
            self.assertEqual(self.client.delete(self.url).status_code, status.HTTP_403_FORBIDDEN)
        with self.subTest("another trainer: 404"):
            self.client.force_authenticate(make_trainer("bo@example.com").user)
            self.assertEqual(self.client.delete(self.url).status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(self.trainer.user)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["status"], "DISCARDED")
        self.talk.refresh_from_db()
        self.assertEqual(self.talk.status, Talk.Status.DISCARDED)

        with self.subTest("discarding again: 409"):
            response = self.client.delete(self.url)
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertEqual(response.json()["code"], "invalid_transition")
