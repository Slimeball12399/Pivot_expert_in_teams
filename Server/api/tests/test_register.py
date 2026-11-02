from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import SpeakerProfile, User

URL = reverse("api:register")


def payload(**overrides):
    data = {
        "email": "speaker@example.com",
        "password": "Str0ng-test-pass!",
        "first_name": "Mikkel",
        "last_name": "Jensen",
        "phone_number": "20 12 34 56",
        "birth_date": "1996-01-01",
        "height_cm": 180,
        "improvement_goals": "Calmer pace",
        "consents": ["privacy_notice"],
    }
    data.update(overrides)
    return data


class RegisterEndpointTests(APITestCase):
    """The HTTP layer. The rules themselves are tested in accounts/tests."""

    def test_registers_speaker(self):
        response = self.client.post(URL, payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get()
        self.assertEqual(response.json(), {
            "id": str(user.id),
            "email": "speaker@example.com",
            "first_name": "Mikkel",
            "last_name": "Jensen",
            "phone_number": "+4520123456",
            "role": "speaker",
        })
        self.assertNotIn("password", response.json())
        self.assertTrue(SpeakerProfile.objects.filter(user=user).exists())
        self.assertEqual(user.consents.count(), 1)

        with self.subTest("improvement goals are optional"):
            data = payload(email="other@example.com")
            del data["improvement_goals"]
            response = self.client.post(URL, data, format="json")
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_rejects_invalid_input(self):
        cases = [
            ("email", {"email": "not-an-email"}),                  # serializer: type
            ("height_cm", {"height_cm": "tall"}),                  # serializer: type
            ("birth_date", {"birth_date": "15-06-2000"}),          # serializer: format
            ("consents", {"consents": ["spam"]}),                  # serializer: unknown choice
            ("birth_date", {"birth_date": "2026-01-01"}),          # accounts: too young
            ("phone_number", {"phone_number": "+36 20 123 4567"}),  # accounts: not Danish
            ("password", {"password": "password"}),                # accounts: too common
            ("consents", {"consents": ["research"]}),              # accounts: privacy notice missing
        ]
        for field, overrides in cases:
            with self.subTest(field=field, **overrides):
                response = self.client.post(URL, payload(**overrides), format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.json())
                self.assertEqual(User.objects.count(), 0)

        for field in payload():
            if field == "improvement_goals":
                continue
            data = payload()
            del data[field]
            with self.subTest("field is required", missing=field):
                response = self.client.post(URL, data, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.json())

        # Last, because it creates a user and the checks above expect none.
        with self.subTest("duplicate email"):
            self.client.post(URL, payload(), format="json")
            response = self.client.post(URL, payload(), format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("email", response.json())
            self.assertEqual(User.objects.count(), 1)

    def test_only_post_is_allowed(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
