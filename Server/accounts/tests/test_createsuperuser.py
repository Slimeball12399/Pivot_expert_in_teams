import os
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.models import AdminProfile

User = get_user_model()

PASSWORD = "Str0ng-test-pass!"
ALL_FIELDS = {
    "email": "trainer@example.com",
    "first_name": "Anna",
    "last_name": "Hansen",
}


def run_createsuperuser(**fields):
    """Run `createsuperuser --noinput` the same way it runs in Docker or CI.

    With --noinput the password is read from DJANGO_SUPERUSER_PASSWORD and
    every field in USERNAME_FIELD + REQUIRED_FIELDS must be passed as an option.
    """
    with mock.patch.dict(os.environ, {"DJANGO_SUPERUSER_PASSWORD": PASSWORD}):
        call_command("createsuperuser", interactive=False, stdout=StringIO(), **fields)


class CreateSuperuserCommandTests(TestCase):
    def test_creates_superuser_with_all_fields(self):
        run_createsuperuser(**ALL_FIELDS)

        user = User.objects.get(email=ALL_FIELDS["email"])
        self.assertEqual(user.first_name, "Anna")
        self.assertEqual(user.last_name, "Hansen")
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))

    def test_creates_admin_profile(self):
        run_createsuperuser(**ALL_FIELDS)

        user = User.objects.get(email=ALL_FIELDS["email"])
        self.assertTrue(AdminProfile.objects.filter(user=user).exists())
        self.assertEqual(user.admin_profile.user, user)

    def test_email_is_normalized(self):
        run_createsuperuser(**{**ALL_FIELDS, "email": "Trainer@EXAMPLE.com"})

        # normalize_email lowercases only the domain part.
        self.assertTrue(User.objects.filter(email="Trainer@example.com").exists())

    def test_requires_email(self):
        fields = {k: v for k, v in ALL_FIELDS.items() if k != "email"}
        with self.assertRaises(CommandError):
            run_createsuperuser(**fields)
        self.assertEqual(User.objects.count(), 0)

    def test_requires_first_name(self):
        fields = {k: v for k, v in ALL_FIELDS.items() if k != "first_name"}
        with self.assertRaises(CommandError):
            run_createsuperuser(**fields)
        self.assertEqual(User.objects.count(), 0)

    def test_requires_last_name(self):
        fields = {k: v for k, v in ALL_FIELDS.items() if k != "last_name"}
        with self.assertRaises(CommandError):
            run_createsuperuser(**fields)
        self.assertEqual(User.objects.count(), 0)

    def test_rejects_duplicate_email(self):
        run_createsuperuser(**ALL_FIELDS)
        with self.assertRaises(CommandError):
            run_createsuperuser(**ALL_FIELDS)
        self.assertEqual(User.objects.count(), 1)


class CreateSuperuserManagerTests(TestCase):
    def test_rejects_non_admin_role(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(password=PASSWORD, role=User.Role.SPEAKER, **ALL_FIELDS)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(AdminProfile.objects.count(), 0)

    def test_rejects_is_staff_false(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(password=PASSWORD, is_staff=False, **ALL_FIELDS)

    def test_rejects_is_superuser_false(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(password=PASSWORD, is_superuser=False, **ALL_FIELDS)
