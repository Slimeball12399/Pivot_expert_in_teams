from datetime import date
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import SpeakerProfile, User
from accounts.services import register_speaker
from accounts.validators import MAX_HEIGHT_CM, MIN_AGE, MIN_HEIGHT_CM

from .utils import FIXED_NOW, frozen_now

# The validators themselves are tested in test_validators.py.
# This file checks what register_speaker adds on top: creating both models,
# that each field's validation is wired up, collecting errors, and rollback.


def speaker_data(**overrides):
    data = {
        "email": "speaker@example.com",
        "password": "Str0ng-test-pass!",
        "first_name": "Mikkel",
        "last_name": "Jensen",
        "phone_number": "+4520123456",
        "birth_date": date(FIXED_NOW.year - 30, 1, 1),
        "height_cm": 180,
        "improvement_goals": "Calmer pace",
    }
    data.update(overrides)
    return data


class RegisterSpeakerTests(TestCase):
    def setUp(self):
        patcher = frozen_now()
        patcher.start()
        self.addCleanup(patcher.stop)

    def assertRejected(self, field, **overrides):
        """Registration fails with an error on `field`, and nothing is saved."""
        with self.assertRaises(ValidationError) as ctx:
            register_speaker(**speaker_data(**overrides))
        self.assertIn(field, ctx.exception.message_dict)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(SpeakerProfile.objects.count(), 0)
        return ctx.exception.message_dict

    # Valid registrations

    def test_creates_user_and_profile(self):
        user = register_speaker(**speaker_data())

        self.assertEqual(user.role, User.Role.SPEAKER)
        self.assertTrue(user.check_password("Str0ng-test-pass!"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

        profile = user.speaker_profile
        self.assertEqual(profile.height_cm, 180)
        self.assertEqual(profile.birth_date, date(FIXED_NOW.year - 30, 1, 1))
        self.assertIsNone(profile.admin)

    def test_improvement_goals_are_optional(self):
        data = speaker_data()
        del data["improvement_goals"]
        user = register_speaker(**data)
        self.assertEqual(user.speaker_profile.improvement_goals, "")

    def test_accepts_height_limits(self):
        for height in [MIN_HEIGHT_CM, MAX_HEIGHT_CM]:
            with self.subTest(height_cm=height):
                user = register_speaker(**speaker_data(email=f"h{height}@example.com", height_cm=height))
                self.assertEqual(user.speaker_profile.height_cm, height)

    def test_danish_number_is_stored_with_country_code(self):
        for i, number in enumerate(["20 12 34 56", "+45 20 12 34 56"]):
            with self.subTest(number=number):
                user = register_speaker(**speaker_data(email=f"s{i}@example.com", phone_number=number))
                self.assertEqual(user.phone_number.as_e164, "+4520123456")

    # Each field's validation is applied

    def test_rejects_invalid_fields(self):
        too_young = date(FIXED_NOW.year - MIN_AGE, FIXED_NOW.month, FIXED_NOW.day + 1)
        cases = [
            ("email", {"email": "not-an-email"}),
            ("first_name", {"first_name": ""}),
            ("last_name", {"last_name": ""}),
            ("password", {"password": "Ab1!"}),                  # too short
            ("password", {"password": "password"}),              # too common
            ("password", {"password": "speaker@example.com"}),   # same as email
            ("phone_number", {"phone_number": ""}),
            ("phone_number", {"phone_number": "123"}),
            ("phone_number", {"phone_number": "+36 20 123 4567"}),  # not Danish
            ("birth_date", {"birth_date": too_young}),
            ("height_cm", {"height_cm": MIN_HEIGHT_CM - 1}),
            ("height_cm", {"height_cm": MAX_HEIGHT_CM + 1}),
        ]
        for field, overrides in cases:
            with self.subTest(field=field, **overrides):
                self.assertRejected(field, **overrides)

    def test_rejects_duplicate_email(self):
        register_speaker(**speaker_data())
        with self.assertRaises(ValidationError) as ctx:
            register_speaker(**speaker_data(first_name="Other"))
        self.assertIn("email", ctx.exception.message_dict)
        self.assertEqual(User.objects.count(), 1)

    # Behaviour of the service as a whole

    def test_reports_user_and_profile_errors_together(self):
        errors = self.assertRejected(
            "password",
            password="Ab1!",
            phone_number="123",
            height_cm=MAX_HEIGHT_CM + 1,
            birth_date=FIXED_NOW.date(),
        )
        for field in ["password", "phone_number", "height_cm", "birth_date"]:
            self.assertIn(field, errors)

    def test_user_is_rolled_back_if_profile_save_fails(self):
        with mock.patch.object(SpeakerProfile, "save", side_effect=RuntimeError("db down")):
            with self.assertRaises(RuntimeError):
                register_speaker(**speaker_data())
        self.assertEqual(User.objects.count(), 0)
