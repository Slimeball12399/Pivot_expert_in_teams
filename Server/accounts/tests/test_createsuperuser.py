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
    """Run `createsuperuser --noinput`, the way it runs in Docker or CI.

    With --noinput the password comes from DJANGO_SUPERUSER_PASSWORD and every
    field in USERNAME_FIELD + REQUIRED_FIELDS must be passed as an option.
    """
    with mock.patch.dict(os.environ, {"DJANGO_SUPERUSER_PASSWORD": PASSWORD}):
        call_command("createsuperuser", interactive=False, stdout=StringIO(), **fields)


class CreateSuperuserCommandTests(TestCase):
    def test_creates_superuser_with_admin_profile(self):
        run_createsuperuser(**{**ALL_FIELDS, "email": "Trainer@EXAMPLE.com"})

        user = User.objects.get()
        self.assertEqual(user.email, "Trainer@example.com")  # domain normalized
        self.assertEqual((user.first_name, user.last_name), ("Anna", "Hansen"))
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(AdminProfile.objects.filter(user=user).exists())

    def test_requires_every_field(self):
        for missing in ALL_FIELDS:
            fields = {k: v for k, v in ALL_FIELDS.items() if k != missing}
            with self.subTest(missing=missing):
                with self.assertRaises(CommandError):
                    run_createsuperuser(**fields)
                self.assertEqual(User.objects.count(), 0)

    def test_rejects_duplicate_email(self):
        run_createsuperuser(**ALL_FIELDS)
        with self.assertRaises(CommandError):
            run_createsuperuser(**ALL_FIELDS)
        self.assertEqual(User.objects.count(), 1)


class CreateSuperuserManagerTests(TestCase):
    def test_rejects_non_superuser_settings(self):
        for override in [
            {"role": User.Role.SPEAKER},
            {"is_staff": False},
            {"is_superuser": False},
        ]:
            with self.subTest(**override):
                with self.assertRaises(ValueError):
                    User.objects.create_superuser(password=PASSWORD, **ALL_FIELDS, **override)
                self.assertEqual(User.objects.count(), 0)
                self.assertEqual(AdminProfile.objects.count(), 0)
