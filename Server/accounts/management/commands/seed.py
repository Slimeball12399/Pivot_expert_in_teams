"""Fill a development database with a trainer, a speaker and an open invite.

    python manage.py seed

Reads from .env (see .env.example):
    SEED_ADMIN_EMAIL     the trainer (an admin), e.g. you
    SEED_SPEAKER_EMAIL   a speaker linked to that trainer
    SEED_INVITE_EMAIL    an email the trainer has invited, not a Pivot user yet
    SEED_PASSWORD        the password of the trainer and the speaker

The trainer and the speaker are marked verified, so they can log in straight
away and no verification codes are emailed. The invite goes through
create_invite(), so its email is printed (SEND_EMAILS=False) or really sent
(SEND_EMAILS=True).

Running it again changes nothing that is already there: existing accounts
keep their password, and an invite that is still open isn't sent again.
Only runs with DJANGO_DEBUG=True, unless --force is given.
"""

import os
from unittest import mock

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Consent, User, UserInvite
from accounts.services.accounts import register_speaker
from accounts.services.invites import create_invite

ENV_VARS = ["SEED_ADMIN_EMAIL", "SEED_SPEAKER_EMAIL", "SEED_INVITE_EMAIL", "SEED_PASSWORD"]

# Placeholders for the fields a speaker must have; change them in the app.
SPEAKER_DETAILS = {
    "first_name": "Test",
    "last_name": "Speaker",
    "phone_number": "20 12 34 56",
    "birth_date": "2000-01-01",
    "height_cm": 180,
}


class Command(BaseCommand):
    help = "Create a trainer, a speaker under them and an open invite, from SEED_* in .env."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Run even when DJANGO_DEBUG is not True (never on a real server).")

    def handle(self, *args, force, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "seed only runs with DJANGO_DEBUG=True (or --force), "
                "so it can't fill a real database by mistake.")
        values = {name: os.environ.get(name, "").strip() for name in ENV_VARS}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise CommandError(f"Set {', '.join(missing)} in .env (see .env.example).")

        try:
            # No verification codes: the seeded accounts are verified below.
            with transaction.atomic(), mock.patch(
                    "accounts.services.accounts.send_verification_code"):
                trainer = self.trainer(values["SEED_ADMIN_EMAIL"], values["SEED_PASSWORD"])
                self.speaker(values["SEED_SPEAKER_EMAIL"], values["SEED_PASSWORD"], trainer)
            # Outside the patch: the invite email is sent as usual.
            with transaction.atomic():
                self.invite(trainer, values["SEED_INVITE_EMAIL"])
        except ValidationError as error:
            raise CommandError(f"Seeding failed: {error}") from error

        self.stdout.write(self.style.SUCCESS("Seeded. Log in with SEED_PASSWORD."))

    def trainer(self, email, password):
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_superuser(
                email, password, first_name="Test", last_name="Trainer")
            self.stdout.write(f"Trainer {email}: created")
        elif user.role != User.Role.ADMIN:
            raise CommandError(f"{email} already exists and is not a trainer.")
        else:
            self.stdout.write(f"Trainer {email}: already there")
        self.verify(user)
        return user.admin_profile

    def speaker(self, email, password, trainer):
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = register_speaker(
                email=email, password=password, consents=Consent.Purpose.values,
                **SPEAKER_DETAILS)
            self.stdout.write(f"Speaker {email}: created")
        elif user.role != User.Role.SPEAKER:
            raise CommandError(f"{email} already exists and is not a speaker.")
        else:
            self.stdout.write(f"Speaker {email}: already there")
        self.verify(user)
        profile = user.speaker_profile
        if profile.admin_id != trainer.pk:
            profile.admin = trainer
            profile.save(update_fields=["admin"])
            self.stdout.write(f"Speaker {email}: linked to {trainer.user.email}")

    def invite(self, trainer, email):
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError(
                f"{email} already has a Pivot account; SEED_INVITE_EMAIL must not.")
        if UserInvite.objects.pending().filter(invited_by=trainer, email__iexact=email).exists():
            self.stdout.write(f"Invite to {email}: already open")
            return
        create_invite(trainer, email)
        self.stdout.write(f"Invite to {email}: sent")

    def verify(self, user):
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])
