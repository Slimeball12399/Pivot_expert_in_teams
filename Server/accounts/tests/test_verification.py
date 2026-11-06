from datetime import timedelta

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import EmailCode, User
from accounts.verification import create_code, validate_code

VERIFY = EmailCode.Purpose.VERIFY_EMAIL
RESET = EmailCode.Purpose.RESET_PASSWORD


def wrong(code):
    """A code of the same length that isn't `code`."""
    return str((int(code) + 1) % 10 ** len(code)).zfill(len(code))


def let_cooldown_pass():
    EmailCode.objects.update(created_at=timezone.now() - timedelta(minutes=5))


class EmailCodeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "anna@example.com", "Str0ng-test-pass!", first_name="Anna", last_name="Hansen")

    @override_settings(EMAIL_CODE_RESEND_COOLDOWN=timedelta(seconds=60))
    def test_create_code(self):
        code = create_code(self.user, VERIFY)
        stored = EmailCode.objects.get()

        with self.subTest("digits, EMAIL_CODE_LENGTH long"):
            self.assertEqual(len(code), settings.EMAIL_CODE_LENGTH)
            self.assertTrue(code.isdigit())

        with self.subTest("only a hash is stored"):
            self.assertNotIn(code, stored.code_hash)
            self.assertEqual(len(stored.code_hash), 64)

        with self.subTest("expires after EMAIL_CODE_LIFETIME"):
            expected = timezone.now() + settings.EMAIL_CODE_LIFETIME
            self.assertAlmostEqual(stored.expires_at, expected, delta=timedelta(seconds=5))

        with self.subTest("nothing new inside the cooldown, per purpose"):
            self.assertIsNone(create_code(self.user, VERIFY))
            self.assertIsNotNone(create_code(self.user, RESET))

        with self.subTest("allowed again after the cooldown"):
            EmailCode.objects.update(created_at=timezone.now() - timedelta(seconds=61))
            self.assertIsNotNone(create_code(self.user, VERIFY))

    @override_settings(EMAIL_CODE_MAX_ATTEMPTS=3)
    def test_validate_code(self):
        code = create_code(self.user, VERIFY)
        other = User.objects.create_user(
            "other@example.com", "Str0ng-test-pass!", first_name="O", last_name="T")

        cases = [
            ("wrong code", self.user, VERIFY, wrong(code)),
            ("other purpose", self.user, RESET, code),
            ("other user", other, VERIFY, code),
            ("empty", self.user, VERIFY, ""),
            ("None", self.user, VERIFY, None),
        ]
        for label, user, purpose, guess in cases:
            with self.subTest("rejects: " + label):
                self.assertFalse(validate_code(user, purpose, guess))

        with self.subTest("right code works once, spaces ignored"):
            EmailCode.objects.update(attempts=0)
            self.assertTrue(validate_code(self.user, VERIFY, f" {code[:4]} {code[4:]} "))
            self.assertFalse(validate_code(self.user, VERIFY, code))

        with self.subTest("expired code"):
            let_cooldown_pass()
            code = create_code(self.user, VERIFY)
            EmailCode.objects.filter(used_at__isnull=True).update(
                expires_at=timezone.now() - timedelta(seconds=1))
            self.assertFalse(validate_code(self.user, VERIFY, code))

        with self.subTest("too many wrong guesses kill the code"):
            let_cooldown_pass()
            code = create_code(self.user, VERIFY)
            for _ in range(3):
                self.assertFalse(validate_code(self.user, VERIFY, wrong(code)))
            self.assertFalse(validate_code(self.user, VERIFY, code))

    def test_new_code_replaces_the_old_one(self):
        old = create_code(self.user, VERIFY)
        reset = create_code(self.user, RESET)
        let_cooldown_pass()
        new = create_code(self.user, VERIFY)
        with self.subTest("the old code is kept, but invalidated"):
            self.assertEqual(EmailCode.objects.filter(purpose=VERIFY).count(), 2)
            self.assertEqual(EmailCode.objects.filter(
                purpose=VERIFY, invalidated_at__isnull=False).count(), 1)
        if old != new:
            self.assertFalse(validate_code(self.user, VERIFY, old))
        self.assertTrue(validate_code(self.user, VERIFY, new))
        with self.subTest("other purposes are left alone"):
            self.assertTrue(validate_code(self.user, RESET, reset))
