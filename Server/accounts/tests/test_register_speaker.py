from datetime import date
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from accounts.models import Consent, SpeakerProfile, User
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
        "consents": ["privacy_notice"],
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

        consent = user.consents.get()
        self.assertEqual(consent.purpose, Consent.Purpose.PRIVACY_NOTICE)
        self.assertEqual(consent.notice_version, Consent.current_version("privacy_notice"))
        self.assertIsNone(consent.withdrawn_at)

    @override_settings(CONSENT_VERSIONS={
        "privacy_notice": "4", "audio_storage": "2", "research": "9"})
    def test_stores_ticked_consents_with_their_own_versions(self):
        # Optional consents are stored, each at its own version, and a
        # purpose sent twice is stored once.
        user = register_speaker(**speaker_data(
            consents=["privacy_notice", "audio_storage", "research", "research"]))
        self.assertEqual(
            dict(user.consents.values_list("purpose", "notice_version")),
            {"privacy_notice": "4", "audio_storage": "2", "research": "9"},
        )
        self.assertEqual(user.consents.count(), 3)

    def test_accepts_valid_variants(self):
        with self.subTest("improvement goals are optional"):
            data = speaker_data(email="goals@example.com")
            del data["improvement_goals"]
            user = register_speaker(**data)
            self.assertEqual(user.speaker_profile.improvement_goals, "")

        for height in [MIN_HEIGHT_CM, MAX_HEIGHT_CM]:
            with self.subTest("height limits are accepted", height_cm=height):
                user = register_speaker(**speaker_data(email=f"h{height}@example.com", height_cm=height))
                self.assertEqual(user.speaker_profile.height_cm, height)

        for i, number in enumerate(["20 12 34 56", "+45 20 12 34 56"]):
            with self.subTest("Danish number is stored with country code", number=number):
                user = register_speaker(**speaker_data(email=f"s{i}@example.com", phone_number=number))
                self.assertEqual(user.phone_number.as_e164, "+4520123456")

    def test_rejects_invalid_input(self):
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
            ("consents", {"consents": []}),                         # privacy notice missing
            ("consents", {"consents": ["research"]}),               # privacy notice missing
            ("consents", {"consents": ["privacy_notice", "spam"]}),  # unknown purpose
        ]
        for field, overrides in cases:
            with self.subTest(field=field, **overrides):
                self.assertRejected(field, **overrides)

        # Last, because it needs an existing user and the rows above expect none.
        with self.subTest("duplicate email"):
            register_speaker(**speaker_data())
            with self.assertRaises(ValidationError) as ctx:
                register_speaker(**speaker_data(first_name="Other"))
            self.assertIn("email", ctx.exception.message_dict)
            self.assertEqual(User.objects.count(), 1)

    def test_service_behaviour(self):
        with self.subTest("user and profile errors are reported together"):
            errors = self.assertRejected(
                "password",
                password="Ab1!",
                phone_number="123",
                height_cm=MAX_HEIGHT_CM + 1,
                birth_date=FIXED_NOW.date(),
            )
            for field in ["password", "phone_number", "height_cm", "birth_date"]:
                self.assertIn(field, errors)

        with self.subTest("the user is rolled back if saving the profile fails"):
            with mock.patch.object(SpeakerProfile, "save", side_effect=RuntimeError("db down")):
                with self.assertRaises(RuntimeError):
                    register_speaker(**speaker_data())
            self.assertEqual(User.objects.count(), 0)
