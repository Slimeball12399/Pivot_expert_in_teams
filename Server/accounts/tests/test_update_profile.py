from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from accounts.services import register_speaker, update_profile

PASSWORD = "Str0ng-test-pass!"


class UpdateProfileTests(TestCase):
    """The rules behind PATCH /api/me/. The serializer only passes "profile"
    for speakers, but update_profile() checks the role itself too."""

    def setUp(self):
        self.speaker = register_speaker(
            email="speaker@example.com", password=PASSWORD,
            first_name="Mikkel", last_name="Jensen", phone_number="20 12 34 56",
            birth_date=date(1996, 1, 1), height_cm=180, consents=["privacy_notice"])
        self.admin = User.objects.create_superuser(
            "admin@example.com", PASSWORD, first_name="Anne", last_name="Admin")

    def test_updates_given_fields(self):
        cases = [
            ("speaker, user field", self.speaker, {"first_name": "Mik"}, {}),
            ("speaker, profile field", self.speaker, {}, {"height_cm": 182}),
            ("speaker, both", self.speaker, {"last_name": "Hansen"}, {"improvement_goals": "Pace"}),
            ("admin, user field", self.admin, {"last_name": "Andersen"}, {}),
            ("nothing", self.speaker, {}, {}),
        ]
        for label, user, fields, profile in cases:
            with self.subTest(label):
                update_profile(user, profile=profile, **fields)
                user.refresh_from_db()
                for name, value in fields.items():
                    self.assertEqual(getattr(user, name), value)
                for name, value in profile.items():
                    self.assertEqual(getattr(user.speaker_profile, name), value)

    def test_admin_profile_is_rejected(self):
        for profile in ({"height_cm": 180}, {"birth_date": date(1990, 1, 1)}):
            with self.subTest(profile=profile):
                with self.assertRaises(ValidationError) as ctx:
                    update_profile(self.admin, profile=profile, last_name="Other")
                self.assertIn("profile", ctx.exception.message_dict)
                self.admin.refresh_from_db()
                self.assertEqual(self.admin.last_name, "Admin")  # nothing saved

    def test_rejects_invalid_values_and_saves_nothing(self):
        cases = [
            ("phone_number", {"phone_number": "+36 20 123 4567"}, {}),
            ("phone_number", {"phone_number": ""}, {}),                # required for speakers
            ("height_cm", {}, {"height_cm": 20}),
            ("birth_date", {}, {"birth_date": date(2999, 1, 1)}),
            ("first_name", {"first_name": ""}, {}),
        ]
        for field, fields, profile in cases:
            with self.subTest(field, **{k: str(v) for k, v in {**fields, **profile}.items()}):
                # A valid change next to the bad one; fields wins if it sets first_name.
                with self.assertRaises(ValidationError) as ctx:
                    update_profile(self.speaker, profile=profile,
                                   **{"first_name": "Changed", **fields})
                self.assertIn(field, ctx.exception.message_dict)
                self.speaker.refresh_from_db()
                self.assertEqual(self.speaker.first_name, "Mikkel")
                self.assertEqual(self.speaker.speaker_profile.height_cm, 180)

    def test_admin_phone_can_be_empty(self):
        """Optional for admins (as in createsuperuser), required for speakers."""
        update_profile(self.admin, phone_number="")
        self.admin.refresh_from_db()
        self.assertEqual(str(self.admin.phone_number), "")

    def test_only_editable_fields(self):
        cases = [
            ("email", {"email": "new@example.com"}, {}),
            ("role", {"role": "admin"}, {}),
            ("profile admin link", {}, {"admin": None}),
        ]
        for label, fields, profile in cases:
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    update_profile(self.speaker, profile=profile, **fields)
