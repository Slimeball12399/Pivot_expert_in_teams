from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from accounts.tests.utils import code_in

PASSWORD = "Str0ng-test-pass!"
NEW_PASSWORD = "An0ther-str0ng-pass!"
REQUEST_URL = reverse("api:password-reset")
VERIFY_URL = reverse("api:password-reset-verify")
CONFIRM_URL = reverse("api:password-reset-confirm")
LOGIN_URL = reverse("api:login")
REFRESH_URL = reverse("api:refresh")


class PasswordResetEndpointTests(APITestCase):
    """The HTTP layer. The rules are tested in accounts/tests/test_password_reset.py."""

    def setUp(self):
        self.user = User.objects.create_user(
            "speaker@example.com", PASSWORD, first_name="Mikkel", last_name="Jensen",
            email_verified_at=timezone.now())

    def request_code(self, email="speaker@example.com"):
        return self.client.post(REQUEST_URL, {"email": email}, format="json")

    def verify(self, code):
        return self.client.post(
            VERIFY_URL, {"email": "speaker@example.com", "code": code}, format="json")

    def confirm(self, uid, token, password=NEW_PASSWORD):
        return self.client.put(
            CONFIRM_URL, {"uid": uid, "reset_token": token, "new_password": password},
            format="json")

    def login(self, password):
        return self.client.post(
            LOGIN_URL, {"email": "speaker@example.com", "password": password}, format="json")

    def test_full_reset(self):
        old_refresh = self.login(PASSWORD).json()["refresh"]

        with self.subTest("request: the same answer for every email"):
            known, unknown = self.request_code(), self.request_code("nobody@example.com")
            self.assertEqual(known.status_code, status.HTTP_200_OK)
            self.assertEqual(known.content, unknown.content)
            self.assertEqual(len(mail.outbox), 1)

        response = self.verify(code_in(mail.outbox[0]))
        with self.subTest("verify: uid + reset_token"):
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
            self.assertEqual(set(response.json()), {"uid", "reset_token"})

        response = self.confirm(response.json()["uid"], response.json()["reset_token"])
        with self.subTest("confirm: a message, no tokens"):
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
            self.assertEqual(set(response.json()), {"detail"})

        with self.subTest("the new password works"):
            self.assertEqual(self.login(NEW_PASSWORD).status_code, status.HTTP_200_OK)

        with self.subTest("the other device is logged out"):
            refresh = self.client.post(REFRESH_URL, {"refresh": old_refresh}, format="json")
            self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects(self):
        self.request_code()
        code = code_in(mail.outbox[0])
        wrong = str((int(code) + 1) % 10 ** len(code)).zfill(len(code))

        with self.subTest("wrong code"):
            response = self.verify(wrong)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.json()["code"], "invalid_code")

        tokens = self.verify(code).json()
        with self.subTest("weak password: field error, the token still works"):
            response = self.confirm(tokens["uid"], tokens["reset_token"], "password")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("new_password", response.json())
            self.assertEqual(self.confirm(tokens["uid"], tokens["reset_token"]).status_code,
                             status.HTTP_200_OK)

        with self.subTest("used token"):
            response = self.confirm(tokens["uid"], tokens["reset_token"], "Yet-an0ther-pass!")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.json()["code"], "invalid_token")

        with self.subTest("missing fields"):
            response = self.client.put(CONFIRM_URL, {}, format="json")
            self.assertEqual(set(response.json()), {"uid", "reset_token", "new_password"})

        for url, method in [(REQUEST_URL, "get"), (VERIFY_URL, "get"),
                            (CONFIRM_URL, "post"), (CONFIRM_URL, "get")]:
            with self.subTest("method not allowed", url=url, method=method):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
