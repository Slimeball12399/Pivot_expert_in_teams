from datetime import timedelta

from django.contrib.auth import SESSION_KEY
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmailCode, User
from accounts.services.accounts import send_verification_code
from accounts.tests.utils import code_in

PASSWORD = "Str0ng-test-pass!"
NEW_PASSWORD = "An0ther-str0ng-pass!"
LOGIN_URL = reverse("web:login")
FORGOT_URL = reverse("web:forgot_password")
CODE_URL = reverse("web:verify_code")
RESEND_URL = reverse("web:resend_code")
RESET_URL = reverse("web:password_reset")


def digits(code):
    """The code as the page posts it: one "code" field per box."""
    return {"code": list(code)}


class CodePagesTests(TestCase):
    """Forgot password -> code -> new password, and login -> code for unverified admins."""

    def setUp(self):
        self.admin = User.objects.create_user(
            "admin@example.com", PASSWORD, first_name="Anna", last_name="Hansen",
            role=User.Role.ADMIN, email_verified_at=timezone.now())

    def login(self, **extra):
        return self.client.post(
            LOGIN_URL, {"email": "admin@example.com", "password": PASSWORD, **extra})

    def test_password_reset(self):
        with self.subTest("login page links to forgot password"):
            self.assertContains(self.client.get(LOGIN_URL), f'href="{FORGOT_URL}"')

        with self.subTest("unknown email: the same next page, no email"):
            self.assertRedirects(self.client.post(FORGOT_URL, {"email": "nobody@example.com"}),
                                 CODE_URL)
            self.assertEqual(len(mail.outbox), 0)

        self.assertRedirects(self.client.post(FORGOT_URL, {"email": "admin@example.com"}), CODE_URL)
        self.assertContains(self.client.get(CODE_URL), "admin@example.com")
        self.assertRedirects(self.client.post(CODE_URL, digits(code_in(mail.outbox[0]))), RESET_URL)

        response = self.client.post(
            RESET_URL, {"new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD})
        # Not fetched here: that would show (and use up) the message.
        self.assertRedirects(response, LOGIN_URL, fetch_redirect_response=False)
        self.assertContains(self.client.get(LOGIN_URL), "Your password is changed.")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(NEW_PASSWORD))

        with self.subTest("the new password page is closed again"):
            self.assertRedirects(self.client.get(RESET_URL), FORGOT_URL)

    def test_email_verification(self):
        self.admin.email_verified_at = None
        self.admin.save()

        with self.subTest("wrong password: the normal error, no code"):
            response = self.login(password="wrong-password")
            self.assertContains(response, "Wrong email or password.")
            self.assertEqual(len(mail.outbox), 0)

        response = self.login(next="/somewhere/")
        self.assertRedirects(response, CODE_URL)
        self.assertNotIn(SESSION_KEY, self.client.session)  # not logged in yet
        self.assertContains(self.client.get(CODE_URL), "Verify your email")

        response = self.client.post(CODE_URL, digits(code_in(mail.outbox[0])))
        self.assertRedirects(response, "/somewhere/", fetch_redirect_response=False)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.admin.pk))
        self.admin.refresh_from_db()
        self.assertIsNotNone(self.admin.email_verified_at)

        with self.subTest("a speaker is verified but not logged in here"):
            self.client.logout()
            User.objects.create_user("speaker@example.com", PASSWORD, first_name="M",
                                     last_name="J", role=User.Role.SPEAKER)
            send_verification_code(User.objects.get(email="speaker@example.com"))
            session = self.client.session
            session["code_flow"] = {"purpose": EmailCode.Purpose.VERIFY_EMAIL,
                                    "email": "speaker@example.com", "next": "", "remember_me": False}
            session.save()
            response = self.client.post(CODE_URL, digits(code_in(mail.outbox[-1])))
            self.assertRedirects(response, LOGIN_URL, fetch_redirect_response=False)
            self.assertNotIn(SESSION_KEY, self.client.session)

    def assertResendWorks(self):
        """On the code page: nothing new inside the cooldown, a new code after it."""
        self.client.post(RESEND_URL)
        self.assertEqual(len(mail.outbox), 1)
        EmailCode.objects.update(created_at=timezone.now() - timedelta(minutes=5))
        self.assertContains(self.client.post(RESEND_URL, follow=True), "we sent a new one")
        self.assertEqual(len(mail.outbox), 2)

    def test_resend(self):
        with self.subTest("password reset"):
            self.client.post(FORGOT_URL, {"email": "admin@example.com"})
            self.assertResendWorks()

        with self.subTest("email verification"):
            mail.outbox.clear()
            EmailCode.objects.all().delete()
            self.admin.email_verified_at = None
            self.admin.save()
            self.login()
            self.assertResendWorks()

    def test_rejects(self):
        with self.subTest("pages need the step before"):
            self.assertRedirects(self.client.get(CODE_URL), LOGIN_URL)
            self.assertRedirects(self.client.post(RESEND_URL), LOGIN_URL)
            self.assertRedirects(self.client.get(RESET_URL), FORGOT_URL)

        for data, message in [({}, "Enter your email."),
                              ({"email": "nope"}, "Enter a valid email address.")]:
            with self.subTest("forgot password form", data=data):
                self.assertContains(self.client.post(FORGOT_URL, data), message)

        self.client.post(FORGOT_URL, {"email": "admin@example.com"})
        code = code_in(mail.outbox[0])
        wrong = str((int(code) + 1) % 10 ** len(code)).zfill(len(code))
        for label, data, message in [
            ("too short", digits(code[:-1]), "-digit code from the email"),
            ("wrong code", digits(wrong), "That code is wrong or has expired"),
        ]:
            with self.subTest("code page: " + label):
                self.assertContains(self.client.post(CODE_URL, data), message)

        self.client.post(CODE_URL, digits(code))  # right code: on to the new password page
        for label, data, message in [
            ("don't match", {"new_password": NEW_PASSWORD, "confirm_password": "other"},
             "The passwords don&#x27;t match."),
            ("too weak", {"new_password": "password", "confirm_password": "password"},
             "This password is too common."),
        ]:
            with self.subTest("new password: " + label):
                self.assertContains(self.client.post(RESET_URL, data), message)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password(PASSWORD))
