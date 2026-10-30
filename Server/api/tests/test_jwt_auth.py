import base64
import json

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

PASSWORD = "Str0ng-test-pass!"
LOGIN_URL = reverse("api:login")
REFRESH_URL = reverse("api:refresh")
LOGOUT_URL = reverse("api:logout")
ME_URL = reverse("api:me")  # any protected endpoint will do


def claims(token):
    """The payload of a JWT: its middle part, readable by anyone."""
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def make_user(email, role):
    return User.objects.create_user(
        email, PASSWORD, first_name="Test", last_name="User", role=role)


class JwtAuthTests(APITestCase):
    """The login, refresh and logout endpoints (Simple JWT, settings.SIMPLE_JWT).
    Login and refresh are public; logout needs the user to be logged in."""

    @classmethod
    def setUpTestData(cls):
        cls.speaker = make_user("speaker@example.com", User.Role.SPEAKER)
        cls.admin = make_user("admin@example.com", User.Role.ADMIN)

    def login(self, email="speaker@example.com", password=PASSWORD):
        return self.client.post(LOGIN_URL, {"email": email, "password": password}, format="json")

    def post(self, url, refresh):
        return self.client.post(url, {"refresh": refresh}, format="json")

    def get_me(self, access):
        return self.client.get(ME_URL, HTTP_AUTHORIZATION=f"Bearer {access}")

    def logout(self, access, refresh):
        return self.client.post(LOGOUT_URL, {"refresh": refresh}, format="json",
                                HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_login(self):
        for user in (self.speaker, self.admin):
            with self.subTest("any role can log in", role=user.role):
                response = self.login(email=user.email)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(set(response.json()), {"access", "refresh"})

        with self.subTest("access token works on a protected endpoint"):
            access = self.login().json()["access"]
            response = self.get_me(access)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()["email"], "speaker@example.com")

        with self.subTest("tokens carry no password hash"):
            payload = claims(self.login().json()["access"])
            self.assertNotIn("hash_password", payload)
            self.assertEqual(payload["user_id"], str(self.speaker.id))

    def test_login_rejects(self):
        cases = [
            ("wrong password", "speaker@example.com", "wrong-password"),
            ("unknown email", "nobody@example.com", PASSWORD),
        ]
        for label, email, password in cases:
            with self.subTest(label):
                response = self.login(email=email, password=password)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertNotIn("access", response.json())

        for field in ("email", "password"):
            data = {"email": "speaker@example.com", "password": PASSWORD}
            del data[field]
            with self.subTest("field is required", missing=field):
                response = self.client.post(LOGIN_URL, data, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.json())

        # Last, because it changes the user.
        with self.subTest("inactive account"):
            self.speaker.is_active = False
            self.speaker.save()
            response = self.login()
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh(self):
        tokens = self.login().json()
        response = self.post(REFRESH_URL, tokens["refresh"])

        with self.subTest("returns a new pair"):
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(set(response.json()), {"access", "refresh"})
            self.assertNotEqual(response.json()["refresh"], tokens["refresh"])

        with self.subTest("new access token works"):
            self.assertEqual(self.get_me(response.json()["access"]).status_code,
                             status.HTTP_200_OK)

        with self.subTest("new refresh token works once more"):
            again = self.post(REFRESH_URL, response.json()["refresh"])
            self.assertEqual(again.status_code, status.HTTP_200_OK)

        with self.subTest("old refresh token was blacklisted"):
            reused = self.post(REFRESH_URL, tokens["refresh"])
            self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rejects(self):
        access = self.login().json()["access"]
        cases = [
            ("not a token", "not-a-token"),
            ("access token instead of refresh", access),
        ]
        for label, token in cases:
            with self.subTest(label):
                response = self.post(REFRESH_URL, token)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        with self.subTest("refresh is required"):
            response = self.client.post(REFRESH_URL, {}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("refresh", response.json())

        with self.subTest("refresh token is not accepted as access token"):
            refresh = self.login().json()["refresh"]
            self.assertEqual(self.get_me(refresh).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout(self):
        tokens = self.login().json()
        response = self.logout(tokens["access"], tokens["refresh"])

        with self.subTest("succeeds"):
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        with self.subTest("refresh token is blacklisted"):
            after = self.post(REFRESH_URL, tokens["refresh"])
            self.assertEqual(after.status_code, status.HTTP_401_UNAUTHORIZED)

        with self.subTest("logging out twice is rejected"):
            again = self.logout(tokens["access"], tokens["refresh"])
            self.assertEqual(again.status_code, status.HTTP_401_UNAUTHORIZED)

        with self.subTest("access token isn't revoked; it expires on its own"):
            self.assertEqual(self.get_me(tokens["access"]).status_code, status.HTTP_200_OK)

    def test_logout_rejects(self):
        tokens = self.login().json()
        cases = [
            # (label, access token in the header or None, refresh token in the body)
            ("not logged in", None, tokens["refresh"]),
            ("garbage access token", "not-a-token", tokens["refresh"]),
            ("refresh token as access token", tokens["refresh"], tokens["refresh"]),
            ("access token in the body", tokens["access"], tokens["access"]),
            ("garbage refresh token", tokens["access"], "not-a-token"),
        ]
        for label, access, refresh in cases:
            with self.subTest(label):
                headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"} if access else {}
                response = self.client.post(LOGOUT_URL, {"refresh": refresh},
                                            format="json", **headers)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED,
                                 response.content)

        with self.subTest("refresh is required"):
            response = self.client.post(LOGOUT_URL, {}, format="json",
                                        HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("refresh", response.json())

        # Last: it uses up the refresh token.
        with self.subTest("rejected attempts blacklist nothing"):
            self.assertEqual(self.post(REFRESH_URL, tokens["refresh"]).status_code,
                             status.HTTP_200_OK)

    def test_public_endpoints_ignore_a_bad_token(self):
        """An app may send an old token on every request; public endpoints
        must still work, not answer 401."""
        bad = {"HTTP_AUTHORIZATION": "Bearer not-a-valid-token"}
        cases = [
            ("health", "get", reverse("api:health"), None, status.HTTP_200_OK),
            ("login", "post", LOGIN_URL,
             {"email": "speaker@example.com", "password": PASSWORD}, status.HTTP_200_OK),
            ("register", "post", reverse("api:register"), {
                "email": "new@example.com", "password": PASSWORD,
                "first_name": "New", "last_name": "Speaker", "phone_number": "20 12 34 56",
                "birth_date": "1996-01-01", "height_cm": 180,
                "consents": ["privacy_notice"],
            }, status.HTTP_201_CREATED),
        ]
        for label, method, url, data, expected in cases:
            with self.subTest(label):
                response = getattr(self.client, method)(url, data, format="json", **bad)
                self.assertEqual(response.status_code, expected, response.content)

    def test_docs_lock_only_protected_endpoints(self):
        """Swagger UI shows a lock when an operation has a "security" entry."""
        schema = self.client.get(reverse("api:schema"), {"format": "json"}).json()
        cases = [
            # (path, method, has lock)
            ("/api/health/", "get", False),
            ("/api/auth/register/", "post", False),
            ("/api/auth/login/", "post", False),
            ("/api/auth/refresh/", "post", False),
            ("/api/auth/logout/", "post", True),
            ("/api/me/", "get", True),
            ("/api/me/", "patch", True),
        ]
        for path, method, locked in cases:
            with self.subTest(f"{method.upper()} {path}", locked=locked):
                operation = schema["paths"][path][method]
                self.assertEqual("security" in operation, locked, operation.get("security"))

    def test_only_post_is_allowed(self):
        access = self.login().json()["access"]
        # Logout checks the login first, so it needs a token to get as far as 405.
        for url in (LOGIN_URL, REFRESH_URL, LOGOUT_URL):
            with self.subTest(url=url):
                response = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {access}")
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
