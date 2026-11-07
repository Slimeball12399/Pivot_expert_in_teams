import uuid
from datetime import timedelta

from django.conf import settings
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User, UserInvite
from accounts.services.invites import (
    INVITE_NOT_FOUND,
    SUGGEST_LIMIT,
    accept_invite,
    create_invite,
    pending_invites_for,
    revoke_invite,
    suggest_invite_emails,
)

from .utils import make_invite, make_speaker, make_trainer

# get_users() is tested in test_trainer_user_view.py, together with the view it reads.


class CreateInviteTests(TestCase):
    def setUp(self):
        self.trainer = make_trainer("anne@example.com")

    def test_creates_the_invite_and_emails_it(self):
        with self.captureOnCommitCallbacks(execute=True):
            invite, registered = create_invite(self.trainer, "  new@EXAMPLE.com ")
        self.assertFalse(registered)
        self.assertEqual(invite.email, "new@example.com")  # domain lowercased, spaces stripped
        self.assertEqual(invite.invited_by, self.trainer)
        self.assertEqual(invite.status, UserInvite.Status.PENDING)
        self.assertAlmostEqual(invite.expires_at - invite.created_at, settings.INVITE_LIFETIME,
                               delta=timedelta(seconds=5))
        self.assertEqual([m.to for m in mail.outbox], [["new@example.com"]])
        self.assertEqual(mail.outbox[0].subject, "You're invited to Pivot")
        self.assertIn("Anne Trainer", mail.outbox[0].body)

        with self.subTest("an email that already has an account"):
            make_speaker("mikkel@example.com")
            _, registered = create_invite(self.trainer, "Mikkel@example.com")
            self.assertTrue(registered)

    def test_resend_replaces_the_open_invite(self):
        first, _ = create_invite(self.trainer, "new@example.com")
        second, _ = create_invite(self.trainer, "new@example.com")
        first.refresh_from_db()
        self.assertEqual(first.status, UserInvite.Status.REVOKED)
        self.assertEqual(second.status, UserInvite.Status.PENDING)

        with self.subTest("another trainer's invite to the same email is untouched"):
            theirs, _ = create_invite(make_trainer("bo@example.com"), "new@example.com")
            create_invite(self.trainer, "new@example.com")
            theirs.refresh_from_db()
            self.assertEqual(theirs.status, UserInvite.Status.PENDING)

    def test_rejects(self):
        make_speaker("mine@example.com", self.trainer)
        cases = [
            ("already one of the trainer's speakers", "MINE@example.com"),
            ("a trainer account", "anne@example.com"),
        ]
        for label, email in cases:
            with self.subTest(label):
                with self.assertRaises(ValidationError) as ctx:
                    create_invite(self.trainer, email)
                self.assertIn("email", ctx.exception.message_dict)
        self.assertEqual(UserInvite.objects.count(), 0)


class RevokeInviteTests(TestCase):
    def setUp(self):
        self.trainer = make_trainer("anne@example.com")
        self.speaker = make_speaker("mikkel@example.com")
        self.invite = make_invite(self.trainer, "Mikkel@example.com")

    def assertNotFound(self, user, invite_id=None):
        with self.assertRaises(ValidationError) as ctx:
            revoke_invite(user, invite_id or self.invite.pk)
        self.assertEqual(ctx.exception.code, INVITE_NOT_FOUND)

    def test_revoke(self):
        cases = [
            ("the trainer cancels", self.trainer.user, UserInvite.Status.REVOKED),
            ("the invited speaker declines", self.speaker, UserInvite.Status.DECLINED),
        ]
        for label, user, expected in cases:
            with self.subTest(label):
                invite = make_invite(self.trainer, "mikkel@example.com")
                revoke_invite(user, invite.pk)
                invite.refresh_from_db()
                self.assertEqual(invite.status, expected)

    def test_not_found(self):
        unverified = make_speaker("unverified@example.com", email_verified_at=None)
        cases = [
            ("another trainer", make_trainer("bo@example.com").user, self.invite),
            ("another speaker", make_speaker("other@example.com"), self.invite),
            ("the invited speaker, unverified", unverified,
             make_invite(self.trainer, "unverified@example.com")),
            ("expired", self.speaker, make_invite(self.trainer, "mikkel@example.com", days_old=10)),
        ]
        for label, user, invite in cases:
            with self.subTest(label):
                self.assertNotFound(user, invite.pk)
        with self.subTest("unknown id"):
            self.assertNotFound(self.speaker, uuid.uuid4())
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, UserInvite.Status.PENDING)

        # Last, because it closes the invite.
        revoke_invite(self.speaker, self.invite.pk)
        for label, user in [("speaker", self.speaker), ("trainer", self.trainer.user)]:
            with self.subTest(f"once declined, the {label} can't revoke it again"):
                self.assertNotFound(user)


class AcceptInviteTests(TestCase):
    def setUp(self):
        self.trainer = make_trainer("anne@example.com")
        self.speaker = make_speaker("mikkel@example.com")
        self.invite = make_invite(self.trainer, "Mikkel@example.com")

    def trainer_of(self, user):
        user.speaker_profile.refresh_from_db()
        return user.speaker_profile.admin

    def test_accept(self):
        other_open = make_invite(make_trainer("bo@example.com"), "mikkel@example.com")
        invite, previous = accept_invite(self.speaker, self.invite.pk)
        self.assertIsNone(previous)
        self.assertEqual(invite.status, UserInvite.Status.ACCEPTED)
        self.assertEqual(invite.accepted_by, self.speaker)
        self.assertEqual(self.trainer_of(self.speaker), self.trainer)

        with self.subTest("the speaker's other open invites are withdrawn"):
            other_open.refresh_from_db()
            self.assertEqual(other_open.status, UserInvite.Status.REVOKED)

    def test_replaces_the_current_trainer(self):
        old_trainer = make_trainer("bo@example.com")
        with self.subTest("another trainer: returned as the previous one"):
            self.speaker.speaker_profile.admin = old_trainer
            self.speaker.speaker_profile.save(update_fields=["admin"])
            _, previous = accept_invite(self.speaker, self.invite.pk)
            self.assertEqual(previous, old_trainer)
            self.assertEqual(self.trainer_of(self.speaker), self.trainer)

        with self.subTest("the same trainer again: no previous one"):
            _, previous = accept_invite(self.speaker,
                                        make_invite(self.trainer, "mikkel@example.com").pk)
            self.assertIsNone(previous)

    def test_not_found(self):
        cases = [
            ("someone else's invite", make_speaker("other@example.com"), self.invite),
            ("a trainer", self.trainer.user, self.invite),
            ("expired", self.speaker, make_invite(self.trainer, "mikkel@example.com", days_old=10)),
            ("declined", self.speaker,
             make_invite(self.trainer, "mikkel@example.com", declined_at=timezone.now())),
            ("revoked", self.speaker,
             make_invite(self.trainer, "mikkel@example.com", revoked_at=timezone.now())),
        ]
        for label, user, invite in cases:
            with self.subTest(label):
                with self.assertRaises(ValidationError) as ctx:
                    accept_invite(user, invite.pk)
                self.assertEqual(ctx.exception.code, INVITE_NOT_FOUND)

        # Last, because it changes the speaker.
        with self.subTest("the invited speaker, unverified"):
            User.objects.filter(pk=self.speaker.pk).update(email_verified_at=None)
            self.speaker.refresh_from_db()
            with self.assertRaises(ValidationError):
                accept_invite(self.speaker, self.invite.pk)

        self.assertIsNone(self.trainer_of(self.speaker))
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, UserInvite.Status.PENDING)


class PendingInvitesForTests(TestCase):
    def test_open_invites_for_the_verified_email(self):
        trainer = make_trainer("anne@example.com")
        speaker = make_speaker("mikkel@example.com")
        open_invite = make_invite(trainer, "MIKKEL@example.com")
        make_invite(trainer, "mikkel@example.com", days_old=1, declined_at=timezone.now())
        make_invite(trainer, "mikkel@example.com", days_old=10)  # expired
        make_invite(trainer, "someone@example.com")

        self.assertEqual(list(pending_invites_for(speaker)), [open_invite])
        with self.subTest("nothing for trainers"):
            self.assertEqual(list(pending_invites_for(trainer.user)), [])
        # Last, because it changes the speaker.
        with self.subTest("nothing while the email is unverified"):
            User.objects.filter(pk=speaker.pk).update(email_verified_at=None)
            speaker.refresh_from_db()
            self.assertEqual(list(pending_invites_for(speaker)), [])


class SuggestInviteEmailsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.trainer = make_trainer("anne@example.com")
        make_speaker("mikkel@example.com", cls.trainer)
        make_speaker("mia@example.com")
        make_speaker("mira@gmail.com")
        make_speaker("mike@example.com", email_verified_at=None)
        make_speaker("milo@example.com", is_active=False)
        make_invite(cls.trainer, "zara@example.com")         # open, no account
        make_invite(cls.trainer, "mira@gmail.com")           # open, a speaker
        make_invite(cls.trainer, "zoe@example.com", days_old=10)  # expired
        make_invite(make_trainer("bo@example.com"), "zak@example.com")  # another trainer's

    def test_suggestions(self):
        cases = [
            ("too short", "mi", []),
            ("from the start, any case, marks the trainer's own", "MIK",
             [{"email": "mikkel@example.com", "already_linked": True, "already_invited": False}]),
            ("someone else's speaker", "mia",
             [{"email": "mia@example.com", "already_linked": False, "already_invited": False}]),
            ("an open invite, no account yet", "zar",
             [{"email": "zara@example.com", "already_linked": False, "already_invited": True}]),
            ("an invited speaker is one entry", "mir",
             [{"email": "mira@gmail.com", "already_linked": False, "already_invited": True}]),
            ("an expired invite isn't", "zoe", []),
            ("another trainer's invite isn't", "zak", []),
            ("a domain finds nothing", "@gmail.com", []),
            ("the middle of an email finds nothing", "kel@ex", []),
            ("trainers are never suggested", "anne", []),
            ("unverified and deactivated accounts aren't", "mil", []),
        ]
        for label, query, expected in cases:
            with self.subTest(label, query=query):
                self.assertEqual(suggest_invite_emails(self.trainer, query), expected)

    def test_at_most_suggest_limit(self):
        for i in range(SUGGEST_LIMIT + 2):
            make_speaker(f"many{i}@example.com")
        self.assertEqual(len(suggest_invite_emails(self.trainer, "many")), SUGGEST_LIMIT)
