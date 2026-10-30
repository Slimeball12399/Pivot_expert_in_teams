from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import SpeakerProfile, User
from accounts.services import register_speaker
from api.serializers import (
    ME_UPDATE_SERIALIZERS,
    AdminMeUpdateSerializer,
    SpeakerMeUpdateSerializer,
)

URL = reverse("api:me")
PASSWORD = "Str0ng-test-pass!"


def error_at(response, path):
    """The errors at "field" or "profile.field" in a 400 body, or None."""
    body = response.json()
    for key in path.split("."):
        if not isinstance(body, dict) or key not in body:
            return None
        body = body[key]
    return body


class MeEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.speaker = register_speaker(
            email="speaker@example.com", password=PASSWORD,
            first_name="Mikkel", last_name="Jensen", phone_number="20 12 34 56",
            birth_date=date(1996, 1, 1), height_cm=180,
            improvement_goals="Calmer pace", consents=["privacy_notice"])
        cls.admin = User.objects.create_superuser(
            "admin@example.com", PASSWORD, first_name="Anne", last_name="Admin")

    def patch(self, data):
        return self.client.patch(URL, data, format="json")

    def assertSpeakerUnchanged(self):
        self.speaker.refresh_from_db()
        self.speaker.speaker_profile.refresh_from_db()
        self.assertEqual(self.speaker.first_name, "Mikkel")
        self.assertEqual(self.speaker.last_name, "Jensen")
        self.assertEqual(str(self.speaker.phone_number), "+4520123456")
        self.assertEqual(self.speaker.speaker_profile.height_cm, 180)
        self.assertEqual(self.speaker.speaker_profile.birth_date, date(1996, 1, 1))

    def test_needs_login(self):
        for method in ("get", "patch"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(URL)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_shape_depends_on_role(self):
        with self.subTest("speaker gets speaker profile"):
            self.client.force_authenticate(self.speaker)
            response = self.client.get(URL)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json(), {
                "id": str(self.speaker.id),
                "email": "speaker@example.com",
                "first_name": "Mikkel",
                "last_name": "Jensen",
                "phone_number": "+4520123456",
                "role": "speaker",
                "profile": {
                    "id": str(self.speaker.speaker_profile.id),
                    "birth_date": "1996-01-01",
                    "height_cm": 180,
                    "improvement_goals": "Calmer pace",
                },
            })
            self.assertNotIn("password", response.json())

        with self.subTest("admin gets admin profile"):
            self.client.force_authenticate(self.admin)
            response = self.client.get(URL)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()["role"], "admin")
            self.assertEqual(response.json()["profile"],
                             {"id": str(self.admin.admin_profile.id)})

        with self.subTest("missing profile row gives null"):
            bare = User.objects.create_user(
                "bare@example.com", PASSWORD, first_name="B", last_name="Are",
                role=User.Role.ADMIN)
            self.client.force_authenticate(bare)
            self.assertIsNone(self.client.get(URL).json()["profile"])

    def test_patch_updates_only_what_is_sent(self):
        self.client.force_authenticate(self.speaker)
        # (label, request body, check on the response body)
        cases = [
            ("user field", {"first_name": "Mik"},
             lambda b: b["first_name"] == "Mik"),
            ("phone is normalised", {"phone_number": "30 11 22 33"},
             lambda b: b["phone_number"] == "+4530112233"),
            ("profile field", {"profile": {"height_cm": 182}},
             lambda b: b["profile"]["height_cm"] == 182),
            ("goals can be cleared", {"profile": {"improvement_goals": ""}},
             lambda b: b["profile"]["improvement_goals"] == ""),
            ("both at once", {"last_name": "Hansen", "profile": {"birth_date": "1995-05-05"}},
             lambda b: b["last_name"] == "Hansen" and b["profile"]["birth_date"] == "1995-05-05"),
            ("empty body changes nothing", {}, lambda b: True),
        ]
        for label, data, check in cases:
            with self.subTest(label):
                before = self.client.get(URL).json()
                response = self.patch(data)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertTrue(check(response.json()))
                self.assertEqual(response.json(), self.client.get(URL).json())  # saved

                # Fields not sent keep their value.
                sent = set(data) | {f"profile.{k}" for k in data.get("profile", {})}
                for key in ("first_name", "last_name", "phone_number"):
                    if key not in sent:
                        self.assertEqual(response.json()[key], before[key], key)
                for key in ("birth_date", "height_cm", "improvement_goals"):
                    if f"profile.{key}" not in sent:
                        self.assertEqual(response.json()["profile"][key],
                                         before["profile"][key], key)

    def test_patch_rejects_invalid_and_saves_nothing(self):
        self.client.force_authenticate(self.speaker)
        cases = [
            ("first_name", {"first_name": ""}),                           # serializer: blank
            ("first_name", {"first_name": "x" * 151}),                    # serializer: too long
            ("phone_number", {"phone_number": ""}),                       # serializer: blank
            ("phone_number", {"phone_number": "+36 20 123 4567"}),        # accounts: not Danish
            ("profile", {"profile": None}),                               # serializer: null
            ("profile.height_cm", {"profile": {"height_cm": "tall"}}),    # serializer: type
            ("profile.height_cm", {"profile": {"height_cm": 20}}),        # accounts: too short
            ("profile.height_cm", {"profile": {"height_cm": 300}}),       # accounts: too tall
            ("profile.birth_date", {"profile": {"birth_date": "05-05-1995"}}),  # serializer: format
            ("profile.birth_date", {"profile": {"birth_date": "2999-01-01"}}),  # accounts: future
            ("profile.birth_date", {"profile": {"birth_date": "2026-01-01"}}),  # accounts: too young
        ]
        for path, data in cases:
            with self.subTest(path, **{k: str(v) for k, v in data.items()}):
                response = self.patch(data)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIsNotNone(error_at(response, path), response.json())
                self.assertSpeakerUnchanged()

        with self.subTest("one bad field stops the valid ones being saved"):
            response = self.patch({
                "first_name": "Changed",
                "phone_number": "+36 20 123 4567",
                "profile": {"height_cm": 20, "improvement_goals": "New"},
            })
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIsNotNone(error_at(response, "phone_number"))
            self.assertIsNotNone(error_at(response, "profile.height_cm"))
            self.assertSpeakerUnchanged()
            self.assertEqual(self.speaker.speaker_profile.improvement_goals, "Calmer pace")

    def test_patch_ignores_read_only_fields(self):
        self.client.force_authenticate(self.speaker)
        cases = [
            ("email", {"email": "new@example.com"}),
            ("role", {"role": "admin"}),
            ("id", {"id": "00000000-0000-0000-0000-000000000000"}),
            ("password", {"password": "N3w-strong-pass!"}),
            ("profile id", {"profile": {"id": "00000000-0000-0000-0000-000000000000"}}),
        ]
        for label, data in cases:
            with self.subTest(label):
                response = self.patch(data)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.speaker.refresh_from_db()
                self.assertEqual(self.speaker.email, "speaker@example.com")
                self.assertEqual(self.speaker.role, User.Role.SPEAKER)
                self.assertTrue(self.speaker.check_password(PASSWORD))
                self.assertEqual(response.json()["profile"]["id"],
                                 str(self.speaker.speaker_profile.id))

    def test_patch_serializer_depends_on_role(self):
        """Speakers get SpeakerMeUpdateSerializer, admins AdminMeUpdateSerializer."""
        cases = [
            ("speaker", self.speaker, SpeakerMeUpdateSerializer, True),
            ("admin", self.admin, AdminMeUpdateSerializer, False),
        ]
        for label, user, serializer_class, has_profile in cases:
            with self.subTest(label):
                self.assertIs(ME_UPDATE_SERIALIZERS[user.role], serializer_class)
                self.assertEqual("profile" in serializer_class().fields, has_profile)
                # Both share the user fields from the base.
                for name in ("first_name", "last_name", "phone_number"):
                    self.assertIn(name, serializer_class().fields)

        with self.subTest("every role has an update serializer"):
            self.assertEqual(set(ME_UPDATE_SERIALIZERS), set(User.Role.values))

    def test_admin_patch_updates_own_details(self):
        self.client.force_authenticate(self.admin)
        cases = [
            ("first name", {"first_name": "Annette"}, "first_name", "Annette"),
            ("last name", {"last_name": "Andersen"}, "last_name", "Andersen"),
            ("phone is normalised", {"phone_number": "20 99 88 77"},
             "phone_number", "+4520998877"),
        ]
        for label, data, field, expected in cases:
            with self.subTest(label):
                response = self.patch(data)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.json()[field], expected)
                self.admin.refresh_from_db()
                self.assertEqual(str(getattr(self.admin, field)), expected)

    def test_admin_patch_ignores_speaker_profile(self):
        self.client.force_authenticate(self.admin)
        admin_profile = {"id": str(self.admin.admin_profile.id)}
        cases = [
            ("profile field", {"profile": {"height_cm": 180}}),
            ("all profile fields", {"profile": {
                "birth_date": "1990-01-01", "height_cm": 180, "improvement_goals": "x"}}),
            ("invalid profile values", {"profile": {"height_cm": "tall", "birth_date": "nope"}}),
            ("profile null", {"profile": None}),
            ("profile not an object", {"profile": "speaker"}),
        ]
        for label, data in cases:
            with self.subTest(label):
                response = self.patch({"last_name": label, **data})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.json()["last_name"], label)  # rest still saved
                self.assertEqual(response.json()["profile"], admin_profile)
                self.assertFalse(SpeakerProfile.objects.filter(user=self.admin).exists())

    def test_admin_patch_rejects_invalid_and_saves_nothing(self):
        self.client.force_authenticate(self.admin)
        cases = [
            ("first_name", {"first_name": ""}),
            ("first_name", {"first_name": "x" * 151}),
            ("last_name", {"last_name": ""}),
            ("phone_number", {"phone_number": "+36 20 123 4567"}),
        ]
        for field, data in cases:
            with self.subTest(field, **{k: v[:20] for k, v in data.items()}):
                # A valid change next to the bad one; data wins if it sets last_name.
                response = self.patch({"last_name": "Changed", **data})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIsNotNone(error_at(response, field), response.json())
                self.admin.refresh_from_db()
                self.assertEqual(self.admin.first_name, "Anne")
                self.assertEqual(self.admin.last_name, "Admin")

    def test_docs_show_both_patch_bodies(self):
        schema = self.client.get(reverse("api:schema"), {"format": "json"}).json()
        components = schema["components"]["schemas"]

        def resolve(node):
            while "$ref" in node:
                node = components[node["$ref"].rsplit("/", 1)[-1]]
            return node

        body = resolve(
            schema["paths"]["/api/me/"]["patch"]["requestBody"]["content"]["application/json"]["schema"])
        options = [resolve(option) for option in body["oneOf"]]
        with_profile = ["profile" in option["properties"] for option in options]

        with self.subTest("two alternatives"):
            self.assertEqual(len(options), 2)
        with self.subTest("one with profile (speaker), one without (admin)"):
            self.assertCountEqual(with_profile, [True, False])
        for option in options:
            with self.subTest("no read-only fields", fields=sorted(option["properties"])):
                for name in ("email", "role", "id", "password"):
                    self.assertNotIn(name, option["properties"])

    def test_only_get_and_patch_are_allowed(self):
        self.client.force_authenticate(self.speaker)
        for method in ("post", "put", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(URL, {}, format="json")
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
