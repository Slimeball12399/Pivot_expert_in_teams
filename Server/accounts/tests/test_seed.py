import os
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import User, UserInvite
from core.models import FullVoiceResult, PartialVoiceResult, Session, Talk

ENV = {
    "SEED_ADMIN_EMAIL": "trainer@example.com",
    "SEED_SPEAKER_EMAIL": "speaker@example.com",
    "SEED_INVITE_EMAIL": "invited@example.com",
    "SEED_PASSWORD": "Str0ng-test-pass!",
    "SEED_SECOND_ADMIN_EMAIL": "",
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
            self.assertEqual(Session.objects.count(), 4)
            self.assertEqual(Talk.objects.count(), 5)

    def test_seeds_sessions_with_talks_and_results(self):
        self.seed()
        speaker = User.objects.get(email="speaker@example.com").speaker_profile

        with self.subTest("four sessions of the speaker with their trainer, none live"):
            sessions = Session.objects.filter(speaker=speaker, trainer=speaker.admin)
            self.assertEqual(
                sorted(sessions.values_list("status", flat=True)),
                sorted(["FINISHED", "FINISHED", "CANCELLED", "NOT_STARTED"]))

        with self.subTest("talks in several statuses; only completed ones have results"):
            self.assertEqual(
                sorted(Talk.objects.values_list("status", flat=True)),
                sorted(["COMPLETED", "COMPLETED", "COMPLETED", "DISCARDED", "FAILED"]))
            self.assertEqual(
                set(FullVoiceResult.objects.values_list("talk__status", flat=True)), {"COMPLETED"})
            self.assertEqual(
                set(PartialVoiceResult.objects.values_list("talk__status", flat=True)), {"COMPLETED"})

        with self.subTest("full scores 0 to 100, window scores -10 to +10"):
            for score in FullVoiceResult.objects.values_list("voice_score", flat=True):
                self.assertTrue(0 <= score <= 100, score)
            for score in PartialVoiceResult.objects.values_list("voice_score", flat=True):
                self.assertTrue(-10 <= score <= 10, score)

        with self.subTest("30 s windows every 5 s that never span the pause"):
            paused = Talk.objects.get(pauses__isnull=False)
            pause = paused.pauses.get()
            windows = list(paused.partial_voice_results.all())
            # 180 recorded seconds split at 90: 13 windows before the pause, 13 after.
            self.assertEqual(len(windows), 26)
            for window in windows:
                self.assertEqual(window.window_length, timedelta(seconds=30))
                window_end = window.start_at + window.window_length
                self.assertTrue(window_end <= pause.paused_at or window.start_at >= pause.resumed_at)
            self.assertEqual(windows[1].start_at - windows[0].start_at, timedelta(seconds=5))

    def test_second_trainer_invites_the_speaker(self):
        self.seed(SEED_SECOND_ADMIN_EMAIL="second@example.com")
        second = User.objects.get(email="second@example.com")
        speaker = User.objects.get(email="speaker@example.com")
        self.assertEqual(second.role, User.Role.ADMIN)
        self.assertEqual(second.get_full_name(), "Second Trainer")
        self.assertEqual(speaker.speaker_profile.admin.user.email, "trainer@example.com")
        invite = UserInvite.objects.get(invited_by=second.admin_profile)
        self.assertEqual(invite.email, "speaker@example.com")
        self.assertEqual(invite.status, UserInvite.Status.PENDING)

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
