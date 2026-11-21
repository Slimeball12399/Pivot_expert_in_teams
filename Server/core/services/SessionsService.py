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
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import SpeakerProfile, User
from core.models import Session, Talk

# Error codes (ValidationError.code) the web views and the API react to.
SPEAKER_NOT_YOURS = "speaker_not_yours"
SPEAKER_INACTIVE = "speaker_inactive"
NOT_ADMIN = "not_admin"
SESSION_NOT_YOURS = "session_not_yours"
INVALID_TRANSITION = "invalid_transition"
SPEAKER_ALREADY_LIVE = "speaker_already_live"

# Default of update_session's optional fields, meaning "leave as it is".
# None can't be used for that, because scheduled_at=None removes the schedule.
UNCHANGED = object()
INVALID_FILTER = "invalid_filter"
INVALID_PAGE = "invalid_page"

# The Sessions page's filters (get_sessions): the session statuses each lists.
SESSION_FILTERS = {
    "past": [Session.Status.FINISHED],
    "upcoming": [Session.Status.NOT_STARTED],
    "discarded": [Session.Status.CANCELLED, Session.Status.ABORTED],
}
# ... and its time filter: the calendar period (UTC) the session's date is in.
SESSION_PERIODS = ["all", "week", "month", "year"]


# --- Create ---

@transaction.atomic
def create_session(
    trainer: User,
    speaker_id: uuid.UUID,
    display: Session.Display = Session.Display.WEB,
    scheduled_at: datetime | None = None,
) -> Session:
    """Creates a NOT_STARTED session of `trainer` (the logged-in admin)
    with one of their speakers, and returns it. `speaker_id` is the
    speaker's user id.

    `scheduled_at` is optional: None means the session is started on the
    spot. A speaker may have several NOT_STARTED sessions; only one can be
    LIVE (enforced by the database). started_at and ended_at stay empty
    until the start and end events fill them in.
    """
    # A speaker that doesn't exist and someone else's speaker give the
    # same error, so the API doesn't reveal which speaker ids exist.
    speaker = (SpeakerProfile.objects.select_related("user", "admin")
               .filter(user_id=speaker_id, admin__user=trainer).first())
    if speaker is None:
        raise ValidationError("This speaker is not one of yours.", code=SPEAKER_NOT_YOURS)
    if not speaker.user.is_active:
        raise ValidationError("This speaker's account is deactivated.", code=SPEAKER_INACTIVE)

    session = Session(
        trainer=speaker.admin,
        speaker=speaker,
        display=display,
        scheduled_at=scheduled_at,
    )
    # The model's validators: display is one of the choices, scheduled_at has
    # a time zone and is in the future. Raises one ValidationError with every
    # field error found.
    session.full_clean()
    session.save()
    return session

# --- Read ---

def list_sessions(
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
    - `speaker_id`: the speaker's user id (the same id create_session() takes), for
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
        sessions = sessions.filter(speaker__user_id=speaker_id)

    return list(sessions.select_related("trainer__user", "speaker__user")
                .order_by("-created_at")[offset:offset + limit])


def get_sessions(trainer, status="past", query="", period="all"):
    """The trainer's sessions for the Sessions page, newest first, the way
    accounts.services.invites.get_users() gives the Users page its rows.
    `trainer` is an AdminProfile.

    status, one of SESSION_FILTERS:
      past       finished
      upcoming   not started yet
      discarded  cancelled or aborted
    A live session is in none of them.

    `query` searches the speaker's first name, last name and email (any
    part).

    Each session has `date`: when it started, else when it is scheduled, else
    when it was created (the date the page shows), and `talk_count`: its talks
    without the discarded ones.

    period, one of SESSION_PERIODS: the calendar period, in UTC, that `date`
    is in, the whole of it (so "week" under upcoming is the rest of this week):
      all    any time
      week   this week, Monday to Sunday
      month  this month
      year   this year
    Raises ValueError for an unknown status or period.
    """
    if status not in SESSION_FILTERS:
        raise ValueError(f"Unknown status: {status}")
    if period not in SESSION_PERIODS:
        raise ValueError(f"Unknown period: {period}")
    sessions = (Session.objects
                .filter(trainer=trainer, status__in=SESSION_FILTERS[status])
                .annotate(date=Coalesce("started_at", "scheduled_at", "created_at")))
    if period != "all":
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "week":
            start = today - timedelta(days=today.weekday())
            end = start + timedelta(days=7)
        elif period == "month":
            start = today.replace(day=1)
            end = (start + timedelta(days=32)).replace(day=1)
        else:
            start = today.replace(month=1, day=1)
            end = start.replace(year=start.year + 1)
        sessions = sessions.filter(date__gte=start, date__lt=end)
    query = query.strip()
    if query:
        sessions = sessions.filter(
            Q(speaker__user__first_name__icontains=query)
            | Q(speaker__user__last_name__icontains=query)
            | Q(speaker__user__email__icontains=query))
    return (sessions.select_related("speaker__user")
            .annotate(talk_count=Count("talks", filter=~Q(talks__status=Talk.Status.DISCARDED)))
            .order_by("-created_at"))

def get_session(user: User, session_id: uuid.UUID) -> Session:
    """Returns the session with its talks if `user` may access it; raises
    otherwise, so the caller stops right there.
    - admin: the sessions they are the trainer of
    - speaker: their own sessions
    Anything else, or a session that doesn't exist, gives session_not_yours
    (the same error, so the API doesn't reveal which session ids exist).
    Callers check the status they need themselves.

    The talks come in the same call (two queries in total):
    session.talks.all() holds them oldest first, without discarded ones, each
    with its full voice result. A talk without one yet raises on
    talk.full_voice_result, so read it with getattr(talk, "full_voice_result", None).
    session.talks.filter(...) still runs its own query over all talks.
    """
    talks = Prefetch(
        "talks",
        queryset=(Talk.objects
                  .exclude(status=Talk.Status.DISCARDED)
                  .select_related("full_voice_result")
                  .order_by("started_at")))
    if user.role == User.Role.ADMIN:
        session = (Session.objects.prefetch_related(talks)
                   .filter(pk=session_id, trainer__user=user).first())
    elif user.role == User.Role.SPEAKER:
        session = (Session.objects.prefetch_related(talks)
                   .filter(pk=session_id, speaker__user=user).first())
    else:
        session = None
    if session is None:
        raise ValidationError("This session is not one of yours.", code=SESSION_NOT_YOURS)
    return session


# --- Update ---

@transaction.atomic
def update_session(
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
        changes["display"] = display
    if scheduled_at is not UNCHANGED:
        changes["scheduled_at"] = scheduled_at
    if not changes:
        return session

    for name, value in changes.items():
        setattr(session, name, value)
    # Only the changed fields are validated, so a schedule that has passed in
    # the meantime doesn't block changing the display.
    session.full_clean(exclude=[field.name for field in Session._meta.concrete_fields
                                if field.name not in changes])
    session.save(update_fields=list(changes))
    return session


# --- State machine events ---

@transaction.atomic
def start_session(trainer: User, session_id: uuid.UUID) -> Session:
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
        session.save(update_fields=["status", "started_at"])
    except IntegrityError as exc:
        if "one_live_session_per_speaker" in str(exc):
            raise ValidationError(
                "This speaker already has a live session.", code=SPEAKER_ALREADY_LIVE) from exc
        raise
    return session


@transaction.atomic
def end_session(trainer: User, session_id: uuid.UUID) -> Session:
    """Ends a live session (LIVE -> FINISHED), sets ended_at and returns it.
    A talk still recording or paused is finished at the same moment
    (-> PROCESSING, with its duration), as if the trainer had finished it."""
    if trainer.role != User.Role.ADMIN:
        raise ValidationError("Only admins can manage sessions.", code=NOT_ADMIN)
    session = get_session(user=trainer, session_id=session_id)
    if session.status != Session.Status.LIVE:
        raise ValidationError(
            "Only a live session can be ended; this one is "
            f"{session.get_status_display().lower()}.",
            code=INVALID_TRANSITION)

    now = timezone.now()
    # From get_session's prefetch, so the returned session shows the change.
    for talk in session.talks.all():
        if talk.status in (Talk.Status.RECORDING, Talk.Status.PAUSED):
            talk.close(Talk.Status.PROCESSING, now)
    session.status = Session.Status.FINISHED
    session.ended_at = now
    session.save(update_fields=["status", "ended_at"])
    return session


@transaction.atomic
def cancel_session(trainer: User, session_id: uuid.UUID) -> Session:
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


@transaction.atomic
def abort_session(trainer: User, session_id: uuid.UUID) -> Session:
    """Aborts a live session that can't go on (LIVE -> ABORTED), e.g. when
    the WebRTC side gives up reconnecting; sets ended_at and returns it. The
    system calls it with the session's trainer, not a button. A talk still
    recording or paused fails at the same moment (-> FAILED), with its
    duration set, so it can be retried if its audio was saved."""
    if trainer.role != User.Role.ADMIN:
        raise ValidationError("Only admins can manage sessions.", code=NOT_ADMIN)
    session = get_session(user=trainer, session_id=session_id)
    if session.status != Session.Status.LIVE:
        raise ValidationError(
            "Only a live session can be aborted; this one is "
            f"{session.get_status_display().lower()}.",
            code=INVALID_TRANSITION)

    now = timezone.now()
    # From get_session's prefetch, so the returned session shows the change.
    for talk in session.talks.all():
        if talk.status in (Talk.Status.RECORDING, Talk.Status.PAUSED):
            talk.close(Talk.Status.FAILED, now)
    session.status = Session.Status.ABORTED
    session.ended_at = now
    session.save(update_fields=["status", "ended_at"])
    return session
