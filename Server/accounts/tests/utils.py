from datetime import datetime, timezone
from unittest import mock

# Tests that depend on "today" run as if it were this moment.
FIXED_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)


def frozen_now(moment=FIXED_NOW):
    """Make datetime.now() in accounts.validators return `moment`.

    Use as a context manager or start()/stop() it in setUp.
    """

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment if tz is not None else moment.replace(tzinfo=None)

    return mock.patch("accounts.validators.datetime", FrozenDatetime)


def code_in(message):
    """The one-time code in a code email (the "1234 5678" line), without spaces."""
    import re

    match = re.search(r"^\s+(\d[\d ]*\d)\s*$", message.body, re.MULTILINE)
    if match is None:
        raise AssertionError(f"No code in the email:\n{message.body}")
    return match.group(1).replace(" ", "")


# Trainers, speakers and invites for the invite tests.

PASSWORD = "Str0ng-test-pass!"


def make_trainer(email):
    """A trainer (admin) named Anne Trainer; returns their AdminProfile."""
    from accounts.models import User

    user = User.objects.create_superuser(
        email, PASSWORD, first_name="Anne", last_name="Trainer")
    return user.admin_profile


def make_speaker(email, trainer=None, **user_fields):
    """A speaker named Mikkel Jensen with a verified email, linked to
    `trainer` (an AdminProfile) if given. user_fields are set on the User
    afterwards, e.g. email_verified_at=None or is_active=False."""
    from django.utils.timezone import now

    from accounts.models import User
    from accounts.services.accounts import register_speaker

    user = register_speaker(
        email=email, password=PASSWORD, first_name="Mikkel", last_name="Jensen",
        phone_number="20 12 34 56", birth_date="1996-01-01", height_cm=180,
        consents=["privacy_notice"])
    User.objects.filter(pk=user.pk).update(**{"email_verified_at": now(), **user_fields})
    if trainer is not None:
        user.speaker_profile.admin = trainer
        user.speaker_profile.save(update_fields=["admin"])
    user.refresh_from_db()
    return user


def make_invite(trainer, email, *, days_old=0, **fields):
    """An invite from `trainer` sent `days_old` days ago, expiring 7 days
    after that (so days_old=10 is expired). fields: e.g. declined_at=now()."""
    from datetime import timedelta

    from django.utils.timezone import now

    from accounts.models import UserInvite

    sent = now() - timedelta(days=days_old)
    invite = UserInvite.objects.create(
        invited_by=trainer, email=email, expires_at=sent + timedelta(days=7), **fields)
    # created_at is auto_now_add, so it can only be moved back afterwards.
    UserInvite.objects.filter(pk=invite.pk).update(created_at=sent)
    invite.refresh_from_db()
    return invite
