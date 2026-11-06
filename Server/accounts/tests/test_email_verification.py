from datetime import timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.services import accounts as account_services
from accounts.models import EmailCode, User
from accounts.services.accounts import (
    EMAIL_NOT_VERIFIED,
    INVALID_CODE,
    INVALID_LOGIN,
    login_user,
    register_speaker,
    resend_verification_code,
    verify_email,
)

from .utils import code_in, frozen_now

PASSWORD = "Str0ng-test-pass!"


def make_user(email="anna@example.com", **extra):
    return User.objects.create_user(
        email, PASSWORD, first_name="Anna", last_name="Hansen", **extra)


def let_cooldown_pass():
    EmailCode.objects.update(created_at=timezone.now() - timedelta(minutes=5))


def wrong(code):
    return str((int(code) + 1) % 10 ** len(code)).zfill(len(code))


class EmailVerificationTests(TestCase):
    def assertRaisesCode(self, code, func, *args):
        with self.assertRaises(ValidationError) as ctx:
            func(*args)
        self.assertEqual(ctx.exception.code, code)

    def test_codes_are_sent(self):
        with self.subTest("after registering"):
            with frozen_now(), self.captureOnCommitCallbacks(execute=True):
                user = register_speaker(
                    email="mikkel@example.com", password=PASSWORD, first_name="Mikkel",
                    last_name="Jensen", phone_number="20 12 34 56", birth_date="1996-01-01",
                    height_cm=180, consents=["privacy_notice"])
            self.assertIsNone(user.email_verified_at)
            self.assertEqual([m.to for m in mail.outbox], [["mikkel@example.com"]])
            self.assertEqual(mail.outbox[0].subject, "Your Pivot verification code")

        with self.subTest("after creating a user in the admin panel"):
            admin = make_user("boss@example.com", role=User.Role.ADMIN, is_staff=True,
                              is_superuser=True, email_verified_at=timezone.now())
            self.client.force_login(admin)
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse("admin:accounts_user_add"), {
                    "email": "trainer@example.com", "first_name": "T", "last_name": "R",
                    "role": "admin", "usable_password": "true",
                    "password1": PASSWORD, "password2": PASSWORD,
                })
            self.assertEqual(response.status_code, 302, getattr(response, "context", None))
            self.assertIsNone(User.objects.get(email="trainer@example.com").email_verified_at)
            self.assertEqual(mail.outbox[-1].to, ["trainer@example.com"])

        with self.subTest("resend: only to unverified accounts, no error otherwise"):
            mail.outbox.clear()
            make_user("new@example.com")
            for email in ("new@example.com", "boss@example.com", "nobody@example.com"):
                resend_verification_code(email)
            self.assertEqual([m.to for m in mail.outbox], [["new@example.com"]])

    def test_login_unverified(self):
        user = make_user()

        with self.subTest("wrong password: the normal error, no code"):
            self.assertRaisesCode(INVALID_LOGIN, login_user, None, "anna@example.com", "wrong")
            self.assertEqual(len(mail.outbox), 0)

        with self.subTest("right password: not verified, and a code"):
            self.assertRaisesCode(EMAIL_NOT_VERIFIED, login_user, None, "anna@example.com", PASSWORD)
            self.assertEqual(len(mail.outbox), 1)

        with self.subTest("again inside the cooldown: no new code"):
            self.assertRaisesCode(EMAIL_NOT_VERIFIED, login_user, None, "anna@example.com", PASSWORD)
            self.assertEqual(len(mail.outbox), 1)

        with self.subTest("after the code, login works"):
            verify_email("anna@example.com", code_in(mail.outbox[0]))
            self.assertEqual(login_user(None, "anna@example.com", PASSWORD), user)

    def test_verify_email(self):
        user = make_user()
        account_services.send_verification_code(user)
        code = code_in(mail.outbox[0])

        cases = [
            ("wrong code", "anna@example.com", wrong(code)),
            ("unknown email", "nobody@example.com", code),
        ]
        for label, email, guess in cases:
            with self.subTest("rejects: " + label):
                self.assertRaisesCode(INVALID_CODE, verify_email, email, guess)

        with self.subTest("rejects: a password reset code"):
            let_cooldown_pass()
            account_services.request_password_reset("anna@example.com")
            self.assertRaisesCode(INVALID_CODE, verify_email, "anna@example.com",
                                  code_in(mail.outbox[-1]))
            user.refresh_from_db()
            self.assertIsNone(user.email_verified_at)

        with self.subTest("right code verifies, once"):
            self.assertEqual(verify_email("anna@example.com", code), user)
            user.refresh_from_db()
            self.assertIsNotNone(user.email_verified_at)
            self.assertRaisesCode(INVALID_CODE, verify_email, "anna@example.com", code)

    def test_changing_email_or_password(self):
        user = make_user(email_verified_at=timezone.now())

        def logged_out(refresh):
            return BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()

        with self.subTest("other changes keep everything"):
            refresh = RefreshToken.for_user(user)
            user.first_name = "Anne"
            user.save()
            user.refresh_from_db()
            self.assertIsNotNone(user.email_verified_at)
            self.assertFalse(logged_out(refresh))

        with self.subTest("new email: unverified, old codes invalidated, code to the new address, logged out"):
            refresh = RefreshToken.for_user(user)
            account_services.request_password_reset("anna@example.com")  # a code to the old address
            mail.outbox.clear()
            user.email = "anna.new@example.com"
            with self.captureOnCommitCallbacks(execute=True):
                user.save()
            user.refresh_from_db()
            self.assertIsNone(user.email_verified_at)
            self.assertEqual([m.to for m in mail.outbox], [["anna.new@example.com"]])
            self.assertEqual(
                list(user.email_codes.filter(invalidated_at__isnull=True).values_list("purpose", flat=True)),
                [EmailCode.Purpose.VERIFY_EMAIL])  # only the new one still works
            self.assertTrue(user.email_codes.filter(
                purpose=EmailCode.Purpose.RESET_PASSWORD, invalidated_at__isnull=False).exists())
            self.assertTrue(logged_out(refresh))

        with self.subTest("an admin setting email_verified_at in the same save wins"):
            verified = timezone.now()
            user.email, user.email_verified_at = "anna@example.com", verified
            user.save()
            user.refresh_from_db()
            self.assertEqual(user.email_verified_at, verified)

        with self.subTest("new password: logged out"):
            refresh = RefreshToken.for_user(user)
            user.set_password("An0ther-str0ng-pass!")
            user.save(update_fields=["password"])
            self.assertTrue(logged_out(refresh))
