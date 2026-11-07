from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserInvite
from accounts.tests.utils import make_invite, make_speaker, make_trainer

LIST_URL = reverse("api:invites")
TRAINER = {"first_name": "Anne", "last_name": "Trainer"}


class InviteEndpointTests(APITestCase):
    """The HTTP layer. The rules are tested in accounts/tests/test_invites.py."""

    def setUp(self):
        self.trainer = make_trainer("anne@example.com")
        self.speaker = make_speaker("mikkel@example.com")
        self.invite = make_invite(self.trainer, "mikkel@example.com")
        self.accept_url = reverse("api:invite-accept", args=[self.invite.pk])
        self.decline_url = reverse("api:invite-decline", args=[self.invite.pk])

    def test_speakers_only(self):
        requests = [("get", LIST_URL), ("post", self.accept_url), ("post", self.decline_url)]
        for method, url in requests:
            with self.subTest("not logged in: 401", url=url):
                self.client.force_authenticate(None)
                self.assertEqual(getattr(self.client, method)(url).status_code,
                                 status.HTTP_401_UNAUTHORIZED)
            with self.subTest("a trainer: 403", url=url):
                self.client.force_authenticate(self.trainer.user)
                self.assertEqual(getattr(self.client, method)(url).status_code,
                                 status.HTTP_403_FORBIDDEN)
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, UserInvite.Status.PENDING)

    def test_list(self):
        self.client.force_authenticate(self.speaker)
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        [item] = response.json()
        self.assertEqual(set(item), {"id", "trainer", "created_at", "expires_at"})
        self.assertEqual(item["id"], str(self.invite.pk))
        self.assertEqual(item["trainer"], TRAINER)

    def test_accept(self):
        self.client.force_authenticate(self.speaker)
        response = self.client.post(self.accept_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        body = response.json()
        self.assertEqual(set(body), {"detail", "trainer", "previous_trainer"})
        self.assertEqual(body["trainer"], TRAINER)
        self.assertIsNone(body["previous_trainer"])
        self.speaker.speaker_profile.refresh_from_db()
        self.assertEqual(self.speaker.speaker_profile.admin, self.trainer)

        with self.subTest("accepting again: 404 invite_not_found"):
            response = self.client.post(self.accept_url)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.json()["code"], "invite_not_found")

        with self.subTest("from another trainer: names the previous one"):
            invite = make_invite(make_trainer("bo@example.com"), "mikkel@example.com")
            response = self.client.post(reverse("api:invite-accept", args=[invite.pk]))
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
            self.assertEqual(response.json()["previous_trainer"], TRAINER)

    def test_decline(self):
        self.client.force_authenticate(self.speaker)
        response = self.client.post(self.decline_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
        self.assertEqual(set(response.json()), {"detail"})
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, UserInvite.Status.DECLINED)

        with self.subTest("declining again: 404 invite_not_found"):
            response = self.client.post(self.decline_url)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.json()["code"], "invite_not_found")

    def test_not_found(self):
        self.client.force_authenticate(make_speaker("other@example.com"))
        for url in (self.accept_url, self.decline_url):
            with self.subTest("someone else's invite", url=url):
                response = self.client.post(url)
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertEqual(response.json()["code"], "invite_not_found")
        with self.subTest("an id that isn't a UUID"):
            self.assertEqual(self.client.post("/api/invites/not-a-uuid/accept/").status_code,
                             status.HTTP_404_NOT_FOUND)
