import uuid
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.tests.utils import make_speaker, make_trainer
from core.models import FullVoiceResult, Session, Talk

LIST_URL = reverse("api:sessions")


class SessionEndpointTests(APITestCase):
    """The HTTP layer. The rules are tested in core/tests/test_session_crud.py."""

    def setUp(self):
        self.trainer = make_trainer("anne@example.com")
        self.speaker = make_speaker("mikkel@example.com", self.trainer)
        self.session = Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile)
        self.url = reverse("api:session", args=[self.session.pk])

    def test_roles(self):
        with self.subTest("not logged in: 401"):
            self.assertEqual(self.client.get(LIST_URL).status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(self.speaker)
        requests = [
            ("post", LIST_URL, {"speaker_id": str(self.speaker.pk)}),
            ("patch", self.url, {"display": "BOTH"}),
            ("delete", self.url, None),
        ]
        for method, url, body in requests:
            with self.subTest(f"a speaker can't {method}: 403"):
                response = getattr(self.client, method)(url, body, format="json")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, Session.Status.NOT_STARTED)

    def test_create(self):
        self.client.force_authenticate(self.trainer.user)
        response = self.client.post(LIST_URL, {
            "speaker_id": str(self.speaker.pk), "display": "BOTH",
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.content)
        body = response.json()
        self.assertEqual(set(body), {
            "id", "status", "speaker", "trainer", "display", "scheduled_at",
            "started_at", "ended_at"})
        self.assertEqual(body["status"], "NOT_STARTED")
        self.assertEqual(body["display"], "BOTH")
        self.assertEqual(body["speaker"]["id"], str(self.speaker.pk))

        with self.subTest("someone else's speaker: 400 with a code"):
            other = make_speaker("lars@example.com", make_trainer("bo@example.com"))
            response = self.client.post(
                LIST_URL, {"speaker_id": str(other.pk)}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.json()["code"], "speaker_not_yours")

        with self.subTest("no speaker_id: 400 on the field"):
            response = self.client.post(LIST_URL, {}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("speaker_id", response.json())

    def test_list(self):
        Session.objects.create(
            trainer=self.trainer, speaker=self.speaker.speaker_profile,
            status=Session.Status.FINISHED)
        for label, user in [("the trainer", self.trainer.user), ("the speaker", self.speaker)]:
            with self.subTest(label):
                self.client.force_authenticate(user)
                self.assertEqual(len(self.client.get(LIST_URL).json()), 2)
                [item] = self.client.get(LIST_URL, {"status": "NOT_STARTED"}).json()
                self.assertEqual(item["id"], str(self.session.pk))

    def test_detail_has_the_talks(self):
        now = timezone.now()
        talk = Talk.objects.create(
            session=self.session, status=Talk.Status.COMPLETED,
            started_at=now - timedelta(minutes=10), duration=timedelta(minutes=4))
        FullVoiceResult.objects.create(talk=talk, voice_score=72.5)
        Talk.objects.create(session=self.session, status=Talk.Status.PROCESSING,
                            started_at=now - timedelta(minutes=5))

        self.client.force_authenticate(self.speaker)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        talks = response.json()["talks"]
        self.assertEqual([t["voice_score"] for t in talks], [72.5, None])
        self.assertEqual(set(talks[0]), {"id", "status", "started_at", "duration", "voice_score"})

        with self.subTest("someone else's session: 404"):
            self.client.force_authenticate(make_trainer("bo@example.com").user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.json()["code"], "session_not_yours")
        with self.subTest("a session that doesn't exist: 404"):
            self.client.force_authenticate(self.trainer.user)
            response = self.client.get(reverse("api:session", args=[uuid.uuid4()]))
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update(self):
        self.client.force_authenticate(self.trainer.user)
        response = self.client.patch(self.url, {"display": "MOBILE"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["display"], "MOBILE")
        self.session.refresh_from_db()
        self.assertEqual(self.session.display, Session.Display.MOBILE)

        with self.subTest("a started session: 409"):
            Session.objects.filter(pk=self.session.pk).update(
                status=Session.Status.LIVE, started_at=timezone.now())
            response = self.client.patch(self.url, {"display": "WEB"}, format="json")
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertEqual(response.json()["code"], "invalid_transition")

    def test_delete_cancels(self):
        self.client.force_authenticate(self.trainer.user)
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(response.json()["status"], "CANCELLED")
        self.assertTrue(Session.objects.filter(pk=self.session.pk).exists())

        with self.subTest("cancelling again: 409"):
            response = self.client.delete(self.url)
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
