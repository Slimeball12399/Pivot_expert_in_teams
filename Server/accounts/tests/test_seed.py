import os
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import User, UserInvite

ENV = {
    "SEED_ADMIN_EMAIL": "trainer@example.com",
    "SEED_SPEAKER_EMAIL": "speaker@example.com",
    "SEED_INVITE_EMAIL": "invited@example.com",
    "SEED_PASSWORD": "Str0ng-test-pass!",
}


@override_settings(DEBUG=True)
class SeedCommandTests(TestCase):
    """python manage.py seed."""

    def seed(self, **env):
        with mock.patch.dict(os.environ, {**ENV, **env}), \
                self.captureOnCommitCallbacks(execute=True):
            call_command("seed", stdout=StringIO())

    def test_seeds_a_trainer_a_speaker_and_an_invite(self):
        self.seed()
        trainer = User.objects.get(email="trainer@example.com")
        speaker = User.objects.get(email="speaker@example.com")

        with self.subTest("the trainer: an admin, verified, with the password"):
            self.assertEqual(trainer.role, User.Role.ADMIN)
            self.assertIsNotNone(trainer.email_verified_at)
            self.assertTrue(trainer.check_password(ENV["SEED_PASSWORD"]))

        with self.subTest("the speaker: verified, linked to the trainer"):
            self.assertEqual(speaker.role, User.Role.SPEAKER)
            self.assertIsNotNone(speaker.email_verified_at)
            self.assertEqual(speaker.speaker_profile.admin, trainer.admin_profile)

        with self.subTest("an open invite, emailed; no verification codes"):
            invite = UserInvite.objects.get()
            self.assertEqual(invite.email, "invited@example.com")
            self.assertEqual(invite.status, UserInvite.Status.PENDING)
            self.assertEqual([message.to for message in mail.outbox], [["invited@example.com"]])

        with self.subTest("running it again changes nothing"):
            self.seed()
            self.assertEqual(User.objects.count(), 2)
            self.assertEqual(UserInvite.objects.count(), 1)
            self.assertEqual(len(mail.outbox), 1)

    def test_rejects(self):
        cases = [
            ("a missing value", {"SEED_PASSWORD": ""}, "SEED_PASSWORD"),
            ("a weak password", {"SEED_PASSWORD": "123"}, "password"),
        ]
        for label, env, message in cases:
            with self.subTest(label):
                with self.assertRaisesMessage(CommandError, message):
                    self.seed(**env)
                self.assertFalse(User.objects.exists())

        with self.subTest("DEBUG off"), override_settings(DEBUG=False):
            with self.assertRaisesMessage(CommandError, "DJANGO_DEBUG=True"):
                self.seed()
