import os
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from accounts.models import AdminProfile, Consent

User = get_user_model()

PASSWORD = "Str0ng-test-pass!"
ALL_FIELDS = {
    "email": "trainer@example.com",
    "first_name": "Anna",
    "last_name": "Hansen",
}


def run_createsuperuser(accept_consents=True, **fields):
    """Run `createsuperuser --noinput`, the way it runs in Docker or CI.

    With --noinput the password comes from DJANGO_SUPERUSER_PASSWORD and every
    field in USERNAME_FIELD + REQUIRED_FIELDS must be passed as an option.
    """
    with mock.patch.dict(os.environ, {"DJANGO_SUPERUSER_PASSWORD": PASSWORD}):
        call_command(
            "createsuperuser",
            interactive=False,
            accept_consents=accept_consents,
            stdout=StringIO(),
            **fields,
        )


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

        # Admins accept every consent, each at its current version.
        self.assertEqual(
            dict(user.consents.values_list("purpose", "notice_version")),
            {purpose: Consent.current_version(purpose) for purpose in Consent.Purpose.values},
        )
        self.assertFalse(user.consents.filter(withdrawn_at__isnull=False).exists())

    def test_consents_must_be_accepted(self):
        with self.subTest("--noinput without --accept-consents is refused"):
            with self.assertRaises(CommandError):
                run_createsuperuser(accept_consents=False, **ALL_FIELDS)
            self.assertEqual(User.objects.count(), 0)
            self.assertEqual(Consent.objects.count(), 0)

        with self.subTest("interactive: asks again on an unclear answer, stops on no"):
            with mock.patch("builtins.input", side_effect=["maybe", "no"]) as fake_input:
                with self.assertRaises(CommandError):
                    call_command("createsuperuser", interactive=True,
                                 stdout=StringIO(), stderr=StringIO())
            self.assertEqual(fake_input.call_count, 2)
            self.assertEqual(User.objects.count(), 0)

        with self.subTest("the env variable counts as accepting"):
            with mock.patch.dict(os.environ, {"DJANGO_SUPERUSER_ACCEPT_CONSENTS": "yes"}):
                run_createsuperuser(accept_consents=False, **ALL_FIELDS)
            self.assertEqual(User.objects.count(), 1)

    def test_rejects_invalid_input(self):
        for missing in ALL_FIELDS:
            fields = {k: v for k, v in ALL_FIELDS.items() if k != missing}
            with self.subTest("every field is required", missing=missing):
                with self.assertRaises(CommandError):
                    run_createsuperuser(**fields)
                self.assertEqual(User.objects.count(), 0)

        # Last, because it creates a user and the rows above expect none.
        with self.subTest("duplicate email"):
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
