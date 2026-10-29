from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from accounts.services import login_user

PASSWORD = "Str0ng-test-pass!"
LOGIN_FAILED = "Wrong email or password."
LOGIN_MISSING_FIELDS = "Enter your email and password."


def make_user(email, role, **extra):
    return User.objects.create_user(
        email, PASSWORD, first_name="Test", last_name="User", role=role, **extra)


class LoginUserTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@example.com", User.Role.ADMIN)
        self.speaker = make_user("speaker@example.com", User.Role.SPEAKER)

    def assertLoginFails(self, message, email, password, role=None):
        with self.assertRaises(ValidationError) as ctx:
            login_user(None, email, password, role=role)
        self.assertEqual(ctx.exception.messages, [message])

    def test_accepts_correct_details(self):
        with self.subTest("admin, limited to admins"):
            self.assertEqual(
                login_user(None, "admin@example.com", PASSWORD, role=User.Role.ADMIN), self.admin)

        with self.subTest("any role when no role is given"):
            self.assertEqual(login_user(None, "speaker@example.com", PASSWORD), self.speaker)
            self.assertEqual(login_user(None, "admin@example.com", PASSWORD), self.admin)

    def test_rejects_with_one_generic_message(self):
        cases = [
            ("wrong password", "admin@example.com", "wrong-password", User.Role.ADMIN),
            ("unknown email", "nobody@example.com", PASSWORD, User.Role.ADMIN),
            ("wrong role", "speaker@example.com", PASSWORD, User.Role.ADMIN),
        ]
        for label, email, password, role in cases:
            with self.subTest(label):
                self.assertLoginFails(LOGIN_FAILED, email, password, role)

        with self.subTest("inactive account"):
            self.admin.is_active = False
            self.admin.save()
            self.assertLoginFails(LOGIN_FAILED, "admin@example.com", PASSWORD, User.Role.ADMIN)

    def test_requires_email_and_password(self):
        for email, password in [("", PASSWORD), ("admin@example.com", ""), ("", ""), (None, None)]:
            with self.subTest(email=email, password=password):
                self.assertLoginFails(LOGIN_MISSING_FIELDS, email, password)
