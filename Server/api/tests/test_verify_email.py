from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import EmailCode, User
from accounts.tests.utils import code_in

PASSWORD = "Str0ng-test-pass!"
LOGIN_URL = reverse("api:login")
URL = reverse("api:verify-email")  # POST: send a code, PUT: verify
ME_URL = reverse("api:me")
REFRESH_URL = reverse("api:refresh")


class EmailVerificationEndpointTests(APITestCase):
    """The HTTP layer. The rules are tested in accounts/tests/test_email_verification.py."""

    def setUp(self):
        self.user = User.objects.create_user(
            "speaker@example.com", PASSWORD, first_name="Mikkel", last_name="Jensen")

    def login(self, password=PASSWORD):
        return self.client.post(
            LOGIN_URL, {"email": "speaker@example.com", "password": password}, format="json")

    def test_unverified_login_then_code(self):
        with self.subTest("wrong password: 401 invalid_login, no code"):
            response = self.login(password="wrong-password")
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertEqual(response.json()["code"], "invalid_login")
            self.assertEqual(len(mail.outbox), 0)

        with self.subTest("right password: 403 email_not_verified, no tokens, a code"):
            response = self.login()
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(response.json()["code"], "email_not_verified")
            self.assertNotIn("access", response.json())
            self.assertEqual(len(mail.outbox), 1)

        with self.subTest("PUT the code: verified, but no tokens"):
            response = self.client.put(
                URL, {"email": "speaker@example.com", "code": code_in(mail.outbox[0])},
                format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
            self.assertEqual(set(response.json()), {"detail"})

        with self.subTest("then the app logs in again and gets tokens"):
            response = self.login()
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            me = self.client.get(ME_URL, HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
            self.assertEqual(me.status_code, status.HTTP_200_OK)

    def test_post_sends_a_code_and_answers_the_same_for_every_email(self):
        User.objects.create_user("done@example.com", PASSWORD, first_name="A",
                                 last_name="B", email_verified_at=timezone.now())
        bodies = set()
        for email in ("speaker@example.com", "done@example.com", "nobody@example.com"):
            # A stale token from an old login must not cause a 401.
            response = self.client.post(URL, {"email": email}, format="json",
                                        HTTP_AUTHORIZATION="Bearer not-a-valid-token")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            bodies.add(response.content)
        self.assertEqual(len(bodies), 1)
        self.assertEqual([m.to for m in mail.outbox], [["speaker@example.com"]])

    def test_rejects(self):
        self.client.post(URL, {"email": "speaker@example.com"}, format="json")
        code = code_in(mail.outbox[0])
        wrong = str((int(code) + 1) % 10 ** len(code)).zfill(len(code))

        for label, data in [
            ("wrong code", {"email": "speaker@example.com", "code": wrong}),
            ("unknown email", {"email": "nobody@example.com", "code": code}),
        ]:
            with self.subTest("PUT: " + label):
                response = self.client.put(URL, data, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.json()["code"], "invalid_code")

        for field in ("email", "code"):
            with self.subTest("PUT: field is required", missing=field):
                data = {"email": "speaker@example.com", "code": code}
                del data[field]
                response = self.client.put(URL, data, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.json())

        with self.subTest("GET is not allowed (sending a code changes things)"):
            self.assertEqual(self.client.get(URL).status_code,
                             status.HTTP_405_METHOD_NOT_ALLOWED)

        with self.subTest("login: malformed email is a 400"):
            response = self.client.post(
                LOGIN_URL, {"email": "not-an-email", "password": PASSWORD}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("email", response.json())

    def test_change_email(self):
        """PATCH /api/me/ asks for it, PUT verify-email with the new email switches it."""
        self.user.email_verified_at = timezone.now()
        self.user.save()
        User.objects.create_user("taken@example.com", PASSWORD, first_name="T", last_name="K")
        tokens = self.login().json()
        auth = {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}

        def patch(data):
            # The code email goes out after the commit.
            with self.captureOnCommitCallbacks(execute=True):
                return self.client.patch(ME_URL, data, format="json", **auth)

        with self.subTest("no email sent: no password needed"):
            response = patch({"first_name": "Mik"})
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
            self.assertEqual(response.json()["first_name"], "Mik")

        for label, data, field in [
            ("wrong password", {"email": "new@example.com", "current_password": "wrong"},
             "current_password"),
            ("no password", {"email": "new@example.com"}, "current_password"),
            ("email taken", {"email": "taken@example.com", "current_password": PASSWORD}, "email"),
        ]:
            with self.subTest("rejects: " + label):
                response = patch(data)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.json())
                self.assertEqual(len(mail.outbox), 0)

        with self.subTest("asking: pending, code to the new address, old email still works"):
            response = patch({"email": "new@example.com", "current_password": PASSWORD})
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
            self.assertEqual(response.json()["email"], "speaker@example.com")
            self.assertEqual(response.json()["pending_email"], "new@example.com")
            self.assertEqual([m.to for m in mail.outbox], [["new@example.com"]])
            self.assertEqual(self.login().status_code, status.HTTP_200_OK)

        with self.subTest("a typo can be fixed: the new address replaces it, the old code dies"):
            old_code = code_in(mail.outbox[0])
            EmailCode.objects.update(created_at=timezone.now() - timedelta(minutes=5))
            patch({"email": "new2@example.com", "current_password": PASSWORD})
            self.assertEqual(mail.outbox[-1].to, ["new2@example.com"])
            response = self.client.put(URL, {"email": "new@example.com", "code": old_code}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        with self.subTest("resend goes to the pending address"):
            EmailCode.objects.update(created_at=timezone.now() - timedelta(minutes=5))
            self.client.post(URL, {"email": "new2@example.com"}, format="json")
            self.assertEqual(mail.outbox[-1].to, ["new2@example.com"])

        with self.subTest("the code switches it, and logs out everywhere"):
            response = self.client.put(
                URL, {"email": "new2@example.com", "code": code_in(mail.outbox[-1])}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
            self.user.refresh_from_db()
            self.assertEqual((self.user.email, self.user.pending_email), ("new2@example.com", ""))
            self.assertIsNotNone(self.user.email_verified_at)
            refresh = self.client.post(REFRESH_URL, {"refresh": tokens["refresh"]}, format="json")
            self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)
            login = self.client.post(
                LOGIN_URL, {"email": "new2@example.com", "password": PASSWORD}, format="json")
            self.assertEqual(login.status_code, status.HTTP_200_OK)

        with self.subTest("sending the current email cancels a pending change"):
            patch({"email": "other@example.com", "current_password": PASSWORD})
            response = patch({"email": "new2@example.com"})
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.content)
            self.assertEqual(response.json()["pending_email"], "")
