from datetime import timedelta
from unittest import mock

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import EmailCode, User
from accounts.services.accounts import (
    INVALID_CODE,
    INVALID_RESET_TOKEN,
    request_password_reset,
    reset_password,
    verify_password_reset_code,
)

from .utils import code_in

PASSWORD = "Str0ng-test-pass!"
NEW_PASSWORD = "An0ther-str0ng-pass!"


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "anna@example.com", PASSWORD, first_name="Anna", last_name="Hansen",
            email_verified_at=timezone.now())

    def reset_token(self):
        """Steps 1 and 2: ask for a code and swap it for (uid, token)."""
        EmailCode.objects.update(created_at=timezone.now() - timedelta(minutes=5))
        request_password_reset("anna@example.com")
        return verify_password_reset_code("anna@example.com", code_in(mail.outbox[-1]))

    def assertRaisesCode(self, code, func, *args):
        with self.assertRaises(ValidationError) as ctx:
            func(*args)
        self.assertEqual(ctx.exception.code, code)

    def test_request_password_reset(self):
        User.objects.create_user("off@example.com", PASSWORD, first_name="O",
                                 last_name="F", is_active=False)
        request_password_reset("anna@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Your Pivot password reset code")

        for label, email in [("unknown email", "nobody@example.com"),
                             ("inactive account", "off@example.com"),
                             ("inside the cooldown", "anna@example.com")]:
            with self.subTest("sends nothing, without an error: " + label):
                request_password_reset(email)
                self.assertEqual(len(mail.outbox), 1)

    def test_full_reset(self):
        self.user.email_verified_at = None  # a reset also proves the email
        self.user.save()
        uid, token = self.reset_token()
        refresh = RefreshToken.for_user(self.user)  # the app logged in somewhere
        # Another reset code asked for before the new password is saved, still open.
        EmailCode.objects.update(created_at=timezone.now() - timedelta(minutes=5))
        request_password_reset("anna@example.com")
        leftover = code_in(mail.outbox[-1])

        self.assertEqual(reset_password(uid, token, NEW_PASSWORD), self.user)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

        with self.subTest("other devices are logged out"):
            self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists())
        with self.subTest("the email counts as verified"):
            self.assertIsNotNone(self.user.email_verified_at)
        with self.subTest("reset codes asked for in the meantime stop working"):
            self.assertRaisesCode(INVALID_CODE, verify_password_reset_code,
                                  "anna@example.com", leftover)
        with self.subTest("the token works once"):
            self.assertRaisesCode(INVALID_RESET_TOKEN, reset_password, uid, token, "Yet-an0ther-pass!")

    @override_settings(PASSWORD_RESET_TIMEOUT=60)
    def test_rejects(self):
        request_password_reset("anna@example.com")
        code = code_in(mail.outbox[0])
        wrong = str((int(code) + 1) % 10 ** len(code)).zfill(len(code))
        for label, email, guess in [("wrong code", "anna@example.com", wrong),
                                    ("unknown email", "nobody@example.com", code)]:
            with self.subTest("no token: " + label):
                self.assertRaisesCode(INVALID_CODE, verify_password_reset_code, email, guess)

        uid, token = self.reset_token()
        for label, args in [
            ("wrong token", (uid, "abc-123")),
            ("garbage uid", ("not-base64!", token)),
            ("other user's uid", ("MTIz", token)),
            ("empty", ("", "")),
        ]:
            with self.subTest("bad token: " + label):
                self.assertRaisesCode(INVALID_RESET_TOKEN, reset_password, *args, NEW_PASSWORD)

        with self.subTest("expired token"):
            later = default_token_generator._now() + timedelta(seconds=61)
            with mock.patch.object(default_token_generator, "_now", return_value=later):
                self.assertRaisesCode(INVALID_RESET_TOKEN, reset_password, uid, token, NEW_PASSWORD)

        with self.subTest("weak password: field error, the token still works"):
            with self.assertRaises(ValidationError) as ctx:
                reset_password(uid, token, "password")
            self.assertIn("new_password", ctx.exception.message_dict)
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password(PASSWORD))
            reset_password(uid, token, NEW_PASSWORD)
