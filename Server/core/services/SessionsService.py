"""Sessions between an admin (trainer) and one of their speakers.

Status changes only happen through the state machine events (start, end,
cancel, abort), never through a plain update; see core/LogicGraphs.md.

Roles are checked where the request comes in (web: only admins log in;
api: api.decorators.role_required). Here every query is scoped to the
user's own sessions or speakers, so a user who isn't the trainer finds
nothing and gets "not yours". get_session decides who may access a
session; the functions that change one also check the admin role first.
"""
import uuid
from collections.abc import Iterable
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import SpeakerProfile, User
from core.models import Session

# Error codes (ValidationError.code) the web views and the API react to.
SPEAKER_NOT_YOURS = "speaker_not_yours"
SPEAKER_INACTIVE = "speaker_inactive"
INVALID_DISPLAY = "invalid_display"
INVALID_SCHEDULE = "invalid_schedule"
NOT_ADMIN = "not_admin"
SESSION_NOT_YOURS = "session_not_yours"
INVALID_TRANSITION = "invalid_transition"
SPEAKER_ALREADY_LIVE = "speaker_already_live"

# Default of update_session's optional fields, meaning "leave as it is".
# None can't be used for that, because scheduled_at=None removes the schedule.
UNCHANGED = object()
INVALID_FILTER = "invalid_filter"
INVALID_PAGE = "invalid_page"



# --- Create ---

def create_session(
    *,
    trainer: User,
    speaker_id: uuid.UUID,
    display: Session.Display = Session.Display.WEB,
    scheduled_at: datetime | None = None,
) -> Session:
    """Creates a NOT_STARTED session of `trainer` (the logged-in admin)
    with one of their speakers, and returns it.

    `scheduled_at` is optional: None means the session is started on the
    spot. A speaker may have several NOT_STARTED sessions; only one can be
    LIVE (enforced by the database). started_at and ended_at stay empty
    until the start and end events fill them in.
    """
    # A speaker that doesn't exist and someone else's speaker give the
    # same error, so the API doesn't reveal which speaker ids exist.
    speaker = (SpeakerProfile.objects.select_related("user", "admin")
               .filter(pk=speaker_id, admin__user=trainer).first())
    if speaker is None:
        raise ValidationError("This speaker is not one of yours.", code=SPEAKER_NOT_YOURS)
    if not speaker.user.is_active:
        raise ValidationError("This speaker's account is deactivated.", code=SPEAKER_INACTIVE)

    if display not in Session.Display.values:
        raise ValidationError(
            f"Display must be one of {', '.join(Session.Display.values)}.",
            code=INVALID_DISPLAY)

    if scheduled_at is not None:
        if timezone.is_naive(scheduled_at):
            raise ValidationError(
                "The scheduled time needs a time zone.", code=INVALID_SCHEDULE)
        if scheduled_at <= timezone.now():
            raise ValidationError(
                "The scheduled time must be in the future.", code=INVALID_SCHEDULE)

    return Session.objects.create(
        trainer=speaker.admin,
        speaker=speaker,
        display=display,
        scheduled_at=scheduled_at,
    )

# --- Read ---

def list_sessions(
    *,
    user: User,
    statuses: Iterable[str] | None = None,
    speaker_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Session]:
    """Sessions `user` may see, newest first. An admin gets the sessions
    they are the trainer of, a speaker their own.

    Filters (optional, combined with AND):
    - `statuses`: e.g. ["NOT_STARTED", "LIVE"]
    - `speaker_id`: a SpeakerProfile id (the same id create_session() takes), for
      an admin listing one speaker's sessions. A speaker only ever sees
      their own sessions, so for them it can only narrow to nothing.
    `limit` (at least 1) and `offset` page through the results; a page
    shorter than `limit` is the last one ("load more" can stop).
    """
    if limit < 1:
        raise ValidationError("Limit must be at least 1.", code=INVALID_PAGE)
    if offset < 0:
        raise ValidationError("Offset can't be negative.", code=INVALID_PAGE)

    if user.role == User.Role.ADMIN:
        sessions = Session.objects.filter(trainer__user=user)
    else:
        sessions = Session.objects.filter(speaker__user=user)

    if statuses:
        unknown = set(statuses) - set(Session.Status.values)
        if unknown:
            raise ValidationError(
                f"Unknown status: {', '.join(sorted(unknown))}.", code=INVALID_FILTER)
        sessions = sessions.filter(status__in=statuses)
    if speaker_id is not None:
        sessions = sessions.filter(speaker_id=speaker_id)

    return list(sessions.select_related("trainer__user", "speaker__user")
                .order_by("-created_at")[offset:offset + limit])

# --- Update ---

def get_session(*, user: User, session_id: uuid.UUID) -> Session:
    """Returns the session if `user` may access it; raises otherwise, so the
    caller stops right there.
    - admin: the sessions they are the trainer of
    - speaker: their own sessions
    Anything else, or a session that doesn't exist, gives session_not_yours
    (the same error, so the API doesn't reveal which session ids exist).
    Callers check the status they need themselves.
    """
    if user.role == User.Role.ADMIN:
        session = Session.objects.filter(pk=session_id, trainer__user=user).first()
    elif user.role == User.Role.SPEAKER:
        session = Session.objects.filter(pk=session_id, speaker__user=user).first()
    else:
        session = None
    if session is None:
        raise ValidationError("This session is not one of yours.", code=SESSION_NOT_YOURS)
    return session


def update_session(
    *,
    trainer: User,
    session_id: uuid.UUID,
    display: Session.Display | object = UNCHANGED,
    scheduled_at: datetime | None | object = UNCHANGED,
) -> Session:
    """Changes the display and/or the scheduled time of a session that hasn't
    started, and returns it.

    Pass only what changes; `scheduled_at=None` removes the schedule. The
    status is never changed here, only through the events below.
    """
    if trainer.role != User.Role.ADMIN:
        raise ValidationError("Only admins can manage sessions.", code=NOT_ADMIN)
    session = get_session(user=trainer, session_id=session_id)
    if session.status != Session.Status.NOT_STARTED:
        raise ValidationError(
            "Only a session that hasn't started can be changed; this one is "
            f"{session.get_status_display().lower()}.",
            code=INVALID_TRANSITION)

    changes = {}
    if display is not UNCHANGED:
        if display not in Session.Display.values:
            raise ValidationError(
                f"Display must be one of {', '.join(Session.Display.values)}.",
                code=INVALID_DISPLAY)
        changes["display"] = display
    if scheduled_at is not UNCHANGED:
        if scheduled_at is not None:
            if timezone.is_naive(scheduled_at):
                raise ValidationError(
                    "The scheduled time needs a time zone.", code=INVALID_SCHEDULE)
            if scheduled_at <= timezone.now():
                raise ValidationError(
                    "The scheduled time must be in the future.", code=INVALID_SCHEDULE)
        changes["scheduled_at"] = scheduled_at

    for name, value in changes.items():
        setattr(session, name, value)
    if changes:
        session.save(update_fields=list(changes))
    return session


# --- State machine events ---

def start_session(*, trainer: User, session_id: uuid.UUID) -> Session:
    """Starts a session (NOT_STARTED -> LIVE), sets started_at and returns it.
    Refused if the speaker already has a LIVE session."""
    if trainer.role != User.Role.ADMIN:
        raise ValidationError("Only admins can manage sessions.", code=NOT_ADMIN)
    session = get_session(user=trainer, session_id=session_id)
    if session.status != Session.Status.NOT_STARTED:
        raise ValidationError(
            "Only a session that hasn't started can be started; this one is "
            f"{session.get_status_display().lower()}.",
            code=INVALID_TRANSITION)

    session.status = Session.Status.LIVE
    session.started_at = timezone.now()
    try:
        # Savepoint, so the constraint error doesn't break a caller's transaction.
        with transaction.atomic():
            session.save(update_fields=["status", "started_at"])
    except IntegrityError as exc:
        if "one_live_session_per_speaker" in str(exc):
            raise ValidationError(
                "This speaker already has a live session.", code=SPEAKER_ALREADY_LIVE) from exc
        raise
    return session


def end_session(*, trainer: User, session_id: uuid.UUID) -> Session:
    """Ends a live session (LIVE -> FINISHED), sets ended_at and returns it."""
    if trainer.role != User.Role.ADMIN:
        raise ValidationError("Only admins can manage sessions.", code=NOT_ADMIN)
    session = get_session(user=trainer, session_id=session_id)
    if session.status != Session.Status.LIVE:
        raise ValidationError(
            "Only a live session can be ended; this one is "
            f"{session.get_status_display().lower()}.",
            code=INVALID_TRANSITION)

    session.status = Session.Status.FINISHED
    session.ended_at = timezone.now()
    session.save(update_fields=["status", "ended_at"])
    return session


def cancel_session(*, trainer: User, session_id: uuid.UUID) -> Session:
    """Cancels a session that hasn't started (NOT_STARTED -> CANCELLED) and
    returns it. Takes the place of deleting: the row stays, so a cancelled
    session doesn't just vanish for the speaker. Started sessions end or
    abort instead."""
    if trainer.role != User.Role.ADMIN:
        raise ValidationError("Only admins can manage sessions.", code=NOT_ADMIN)
    session = get_session(user=trainer, session_id=session_id)
    if session.status != Session.Status.NOT_STARTED:
        raise ValidationError(
            "Only a session that hasn't started can be cancelled; this one is "
            f"{session.get_status_display().lower()}.",
            code=INVALID_TRANSITION)

    session.status = Session.Status.CANCELLED
    session.save(update_fields=["status"])
    return session
