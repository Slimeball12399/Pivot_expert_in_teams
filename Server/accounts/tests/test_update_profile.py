from datetime import date, timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import EmailCode, User
from accounts.services import register_speaker, update_profile, verify_email

from .utils import code_in

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
            ("role", {"role": "admin"}, {}),
            ("profile admin link", {}, {"admin": None}),
        ]
        for label, fields, profile in cases:
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    update_profile(self.speaker, profile=profile, **fields)

    def test_change_email(self):
        """A new email needs the password and only becomes pending_email."""
        def assertFails(field, **fields):
            with self.assertRaises(ValidationError) as ctx:
                update_profile(self.speaker, **fields)
            self.assertIn(field, ctx.exception.message_dict)
            self.speaker.refresh_from_db()
            self.assertEqual(self.speaker.pending_email, "")

        with self.subTest("no email sent: no password needed"):
            update_profile(self.speaker, first_name="Mik")
            self.speaker.refresh_from_db()
            self.assertEqual(self.speaker.first_name, "Mik")

        with self.subTest("rejects: wrong password"):
            assertFails("current_password", email="new@example.com", current_password="wrong")
        with self.subTest("rejects: no password"):
            assertFails("current_password", email="new@example.com")
        with self.subTest("rejects: email taken"):
            assertFails("email", email="admin@example.com", current_password=PASSWORD)

        with self.subTest("right password: pending, code to the new address, email unchanged"):
            with self.captureOnCommitCallbacks(execute=True):
                update_profile(self.speaker, email="new@example.com", current_password=PASSWORD)
            self.speaker.refresh_from_db()
            self.assertEqual(self.speaker.email, "speaker@example.com")
            self.assertEqual(self.speaker.pending_email, "new@example.com")
            self.assertEqual(mail.outbox[-1].to, ["new@example.com"])

        with self.subTest("the current email cancels it, no password needed"):
            update_profile(self.speaker, email="speaker@example.com")
            self.speaker.refresh_from_db()
            self.assertEqual(self.speaker.pending_email, "")

    def test_pending_email_holds_the_address_while_it_can_be_confirmed(self):
        with self.captureOnCommitCallbacks(execute=True):
            update_profile(self.speaker, email="new@example.com", current_password=PASSWORD)

        for email in ("new@example.com", "NEW@example.com"):
            with self.subTest("another account can't take it", email=email):
                with self.assertRaises(ValidationError) as ctx:
                    update_profile(self.admin, email=email, current_password=PASSWORD)
                self.assertIn("email", ctx.exception.message_dict)

        with self.subTest("once its code has expired, another account can take it"):
            EmailCode.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
            update_profile(self.admin, email="new@example.com", current_password=PASSWORD)
            self.admin.refresh_from_db()
            self.speaker.refresh_from_db()
            self.assertEqual(self.admin.pending_email, "new@example.com")
            self.assertEqual(self.speaker.pending_email, "")  # the stale one is cleared

    def test_email_taken_in_other_letter_case(self):
        with self.assertRaises(ValidationError) as ctx:
            update_profile(self.speaker, email="Admin@Example.com", current_password=PASSWORD)
        self.assertIn("email", ctx.exception.message_dict)

    def test_code_for_an_earlier_pending_email_does_not_confirm_a_new_one(self):
        with self.captureOnCommitCallbacks(execute=True):
            update_profile(self.speaker, email="mine@example.com", current_password=PASSWORD)
        code = code_in(mail.outbox[-1])
        # Inside the resend cooldown, so no new code is sent for this one.
        update_profile(self.speaker, email="someone@example.com", current_password=PASSWORD)

        for email in ("someone@example.com", "mine@example.com"):
            with self.subTest(email=email):
                with self.assertRaises(ValidationError):
                    verify_email(email, code)
        self.speaker.refresh_from_db()
        self.assertEqual(self.speaker.email, "speaker@example.com")

    def test_sending_the_same_pending_email_again_keeps_its_code(self):
        with self.captureOnCommitCallbacks(execute=True):
            update_profile(self.speaker, email="new@example.com", current_password=PASSWORD)
        code = code_in(mail.outbox[-1])
        update_profile(self.speaker, email="new@example.com", current_password=PASSWORD)
        verify_email("new@example.com", code)
        self.speaker.refresh_from_db()
        self.assertEqual(self.speaker.email, "new@example.com")

    def test_confirming_keeps_the_spelling_that_was_saved(self):
        with self.captureOnCommitCallbacks(execute=True):
            update_profile(self.speaker, email="New.Name@example.com", current_password=PASSWORD)
        verify_email("new.name@EXAMPLE.com", code_in(mail.outbox[-1]))
        self.speaker.refresh_from_db()
        self.assertEqual(self.speaker.email, "New.Name@example.com")
        self.assertEqual(self.speaker.pending_email, "")
