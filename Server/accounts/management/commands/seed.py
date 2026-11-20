"""Fill a development database with a trainer, a speaker, an open invite, and
sessions with talks and voice results.

    python manage.py seed

Reads from .env (see .env.example):
    SEED_ADMIN_EMAIL     the trainer (an admin), e.g. you
    SEED_SPEAKER_EMAIL   a speaker linked to that trainer
    SEED_INVITE_EMAIL    an email the trainer has invited, not a Pivot user yet
    SEED_PASSWORD        the password of the trainer and the speaker
    SEED_SECOND_ADMIN_EMAIL  optional: a second trainer ("Second Trainer")
                         who invites the speaker, to try switching trainers

The trainer and the speaker are marked verified, so they can log in straight
away and no verification codes are emailed. The invite goes through
create_invite(), so its email is printed (SEND_EMAILS=False) or really sent
(SEND_EMAILS=True).

The speaker gets sessions with the trainer, to try the session and talk
screens: one finished last week, one cancelled, one finished yesterday and
one scheduled for tomorrow. Completed talks have a full voice result (score
0 to 100) and partial results: 30 s windows every 5 s that never span a
pause, scored -10 to +10. The values are made up but the same on every run.
No session is left live, so one can be started by hand.

Running it again changes nothing that is already there: existing accounts
keep their password, an invite that is still open isn't sent again, and a
speaker who already has sessions gets no new ones.
A speaker who accepted the second trainer's invite is moved back to the
first trainer and invited again, so the switch can be tried again.
Only runs with DJANGO_DEBUG=True, unless --force is given.
"""

import os
import random
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Consent, User, UserInvite
from accounts.services.accounts import register_speaker
from accounts.services.invites import create_invite
from core.models import FullVoiceResult, PartialVoiceResult, Session, Talk

ENV_VARS = ["SEED_ADMIN_EMAIL", "SEED_SPEAKER_EMAIL", "SEED_INVITE_EMAIL", "SEED_PASSWORD"]

# Placeholders for the fields a speaker must have; change them in the app.
SPEAKER_DETAILS = {
    "first_name": "Test",
    "last_name": "Speaker",
    "phone_number": "20 12 34 56",
    "birth_date": "2000-01-01",
    "height_cm": 180,
}

# The live analysis windows (Design decisions, 4B): 30 s long, one every 5 s.
WINDOW_SECONDS = 30
STEP_SECONDS = 5


class Command(BaseCommand):
    help = ("Create a trainer, a speaker under them, an open invite and sessions "
            "with talks and voice results, from SEED_* in .env.")

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
        second_admin_email = os.environ.get("SEED_SECOND_ADMIN_EMAIL", "").strip()

        try:
            # No verification codes: the seeded accounts are verified below.
            with transaction.atomic(), mock.patch(
                    "accounts.services.accounts.send_verification_code"):
                trainer = self.trainer(values["SEED_ADMIN_EMAIL"], values["SEED_PASSWORD"], "Test")
                speaker = self.speaker(
                    values["SEED_SPEAKER_EMAIL"], values["SEED_PASSWORD"], trainer)
                self.sessions(speaker)
                second_trainer = None
                if second_admin_email:
                    second_trainer = self.trainer(
                        second_admin_email, values["SEED_PASSWORD"], "Second")
            if User.objects.filter(email__iexact=values["SEED_INVITE_EMAIL"]).exists():
                raise CommandError(
                    f"{values['SEED_INVITE_EMAIL']} already has a Pivot account; "
                    "SEED_INVITE_EMAIL must not.")
            # Outside the patch: the invite emails are sent as usual.
            with transaction.atomic():
                self.invite(trainer, values["SEED_INVITE_EMAIL"])
            # Accepting this one in the app replaces the first trainer.
            if second_trainer is not None:
                with transaction.atomic():
                    self.invite(second_trainer, values["SEED_SPEAKER_EMAIL"])
        except ValidationError as error:
            raise CommandError(f"Seeding failed: {error}") from error

        self.stdout.write(self.style.SUCCESS("Seeded. Log in with SEED_PASSWORD."))

    def trainer(self, email, password, first_name):
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_superuser(
                email, password, first_name=first_name, last_name="Trainer")
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
        return profile

    def sessions(self, speaker):
        """Sessions of the speaker with their trainer, with talks, pauses and
        voice results. Skipped when the speaker already has sessions."""
        email = speaker.user.email
        if speaker.sessions.exists():
            self.stdout.write(f"Sessions of {email}: already there")
            return
        rng = random.Random(42)  # the same values on every run
        now = timezone.now()
        trainer = speaker.admin
        between_talks = timedelta(minutes=3)

        # Created oldest first, so list_sessions (newest first) shows them in order.
        last_week = Session.objects.create(
            trainer=trainer, speaker=speaker, status=Session.Status.FINISHED,
            display=Session.Display.WEB, started_at=now - timedelta(days=7))
        ended = self.talk(rng, last_week, last_week.started_at + timedelta(minutes=2), 300)
        ended = self.talk(rng, last_week, ended + between_talks, 120, Talk.Status.FAILED)
        last_week.ended_at = ended + timedelta(minutes=2)
        last_week.save(update_fields=["ended_at"])

        Session.objects.create(
            trainer=trainer, speaker=speaker, status=Session.Status.CANCELLED,
            scheduled_at=now - timedelta(days=3))

        yesterday = Session.objects.create(
            trainer=trainer, speaker=speaker, status=Session.Status.FINISHED,
            display=Session.Display.BOTH, started_at=now - timedelta(days=1))
        ended = self.talk(rng, yesterday, yesterday.started_at + timedelta(minutes=2), 240)
        ended = self.talk(rng, yesterday, ended + between_talks, 90, Talk.Status.DISCARDED)
        # Paused after 90 recorded seconds, for 45 seconds.
        ended = self.talk(rng, yesterday, ended + between_talks, 180, pause=(90, 45))
        yesterday.ended_at = ended + timedelta(minutes=2)
        yesterday.save(update_fields=["ended_at"])

        Session.objects.create(
            trainer=trainer, speaker=speaker, status=Session.Status.NOT_STARTED,
            scheduled_at=now + timedelta(days=1))
        self.stdout.write(f"Sessions of {email}: 4 created, with talks and voice results")

    def talk(self, rng, session, started_at, seconds, status=Talk.Status.COMPLETED, pause=None):
        """A talk with `seconds` recorded seconds, starting at `started_at`;
        returns when it ended. `pause` is (after how many recorded seconds,
        for how many seconds) and becomes a TalkPause. A completed talk gets a
        full voice result and partial results; the windows stay inside the
        recorded stretches, as the live analysis clears its buffer on pause."""
        talk = Talk.objects.create(
            session=session, status=status, started_at=started_at,
            duration=timedelta(seconds=seconds),
            analysis_attempts=3 if status == Talk.Status.FAILED else 0)
        # Recorded stretches: (first recorded second, end, real time it starts).
        stretches = [(0, seconds, started_at)]
        ended_at = started_at + timedelta(seconds=seconds)
        if pause is not None:
            after, length = pause
            paused_at = started_at + timedelta(seconds=after)
            resumed_at = paused_at + timedelta(seconds=length)
            talk.pauses.create(paused_at=paused_at, resumed_at=resumed_at)
            stretches = [(0, after, started_at), (after, seconds, resumed_at)]
            ended_at += timedelta(seconds=length)
        if status != Talk.Status.COMPLETED:
            return ended_at

        windows = []
        score = rng.uniform(-3, 3)
        for first, end, real_start in stretches:
            for second in range(first, end - WINDOW_SECONDS + 1, STEP_SECONDS):
                # Drifts from window to window, like a real talk.
                score = min(10.0, max(-10.0, score + rng.uniform(-1.5, 1.5)))
                windows.append(PartialVoiceResult(
                    talk=talk, start_at=real_start + timedelta(seconds=second - first),
                    window_length=timedelta(seconds=WINDOW_SECONDS),
                    voiced_seconds=round(rng.uniform(18, 27), 1),
                    voice_score=round(score, 1), **voice_measures(rng)))
        PartialVoiceResult.objects.bulk_create(windows)
        FullVoiceResult.objects.create(
            talk=talk, voice_score=round(rng.uniform(55, 90), 1),
            mean_pause_duration=round(rng.uniform(0.4, 0.9), 2),
            pause_frequency=round(rng.uniform(6, 14), 1),
            spl_dbfs=round(rng.uniform(-30, -20), 1),
            **voice_measures(rng))
        return ended_at

    def invite(self, trainer, email):
        if UserInvite.objects.pending().filter(invited_by=trainer, email__iexact=email).exists():
            self.stdout.write(f"Invite to {email}: already open")
            return
        # Confirmed: the second trainer's invite is meant to replace the first.
        create_invite(trainer, email, True)
        self.stdout.write(f"Invite to {email}: sent")

    def verify(self, user):
        if user.email_verified_at is None:
            user.email_verified_at = timezone.now()
            user.save(update_fields=["email_verified_at"])


def voice_measures(rng):
    """Plausible made-up values for the measures on every voice result."""
    return {
        "mean_f0": round(rng.gauss(125, 15), 1),
        "f0_range_q90_q10": round(rng.gauss(45, 10), 1),
        "mean_f1": round(rng.gauss(520, 40), 1),
        "mean_f2": round(rng.gauss(1500, 120), 1),
        "mean_f3": round(rng.gauss(2500, 150), 1),
        "h1_h2_corrected": round(rng.gauss(4, 1.5), 2),
        "h1_a3_corrected": round(rng.gauss(20, 4), 2),
        "mean_speaking_rate": round(rng.gauss(4.5, 0.5), 2),
    }
