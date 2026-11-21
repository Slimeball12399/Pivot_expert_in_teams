"""Session pages: the Sessions page (list for now empty) with creating a
session from the new session dialog, and the talk screen (talk.html, the
screen while a talk is going on, with no URL yet). The dialog's user search
is web:invite_suggestions with own=1 (web/views/users.py)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse, QueryDict
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.models import User
from core.models import Session, Talk
from core.services.GraphsService import get_talk_graphs
from core.services.SessionsService import (
    SESSION_FILTERS,
    SESSION_NOT_YOURS,
    SESSION_PERIODS,
    create_session,
    delete_session,
    get_session,
    get_sessions,
    update_session,
)
from core.services.TalksService import get_talk

from ..decorators import role_required
from ..forms import SessionBaseForm, SessionCreateForm

# The status filter (?status=), one at a time. The values are the keys of
# SESSION_FILTERS, which says which sessions each one lists.
STATUS_OPTIONS = [
    {"value": "past", "label": "Past"},
    {"value": "upcoming", "label": "Upcoming"},
    {"value": "discarded", "label": "Discarded"},
]
DEFAULT_STATUS = "past"
# The time filter (?period=), one at a time; the values are SESSION_PERIODS.
PERIOD_OPTIONS = [
    {"value": "all", "label": "All time"},
    {"value": "week", "label": "This week"},
    {"value": "month", "label": "This month"},
    {"value": "year", "label": "This year"},
]
DEFAULT_PERIOD = "all"

# The voice graph on the talk screen: pace (the solid line) and pitch
# variation (the dashed one, second_points) as scores from -10 to +10, with the
# optimal band from -5 to +5. Live: it shows the minute the newest score is in
# and moves on to the next minute as the data gets there. No data until there
# is a live talk; talk.js writes demo data into it for now.
VOICE_CHART = {
    "measure": "speech",
    "live": True,
    "x": {"min": 0, "interval": 10, "window": 60},
    "y": {"min": -10, "max": 10, "interval": 5},
    "target": {"low": -5, "high": 5},
    "points": [],
    "second_points": [],
}


@require_http_methods(["GET", "POST"])
@role_required(User.Role.ADMIN)
def session_list(request):
    """GET: the Sessions page: the head (numbers, search ?q= by the user's
    name or email, New session, which opens the new session dialog), the
    filters (?status=, see SESSION_FILTERS, default past; ?period=, see
    SESSION_PERIODS, default all; an unknown value falls back to the
    default) and the sessions table from get_sessions(), newest first.

    POST: create a session, from the new session dialog
    (new-session-dialog.js posts the form). 201 {"id": ...}: created; the
    message also waits as a toast for the reload. 400 {"errors": {field:
    [...]}}: shown in the dialog, which stays open. "now" only creates the
    session for now (scheduled_at stays empty); starting it comes later."""
    if request.method == "GET":
        status = request.GET.get("status", DEFAULT_STATUS)
        if status not in SESSION_FILTERS:
            status = DEFAULT_STATUS
        period = request.GET.get("period", DEFAULT_PERIOD)
        if period not in SESSION_PERIODS:
            period = DEFAULT_PERIOD
        query = request.GET.get("q", "").strip()
        rows = list(get_sessions(
            request.user.admin_profile, status, query, period))
        for row in rows:
            # Whole minutes from start to end; None until it has ended.
            row.minutes = (round((row.ended_at - row.started_at).total_seconds() / 60)
                           if row.started_at and row.ended_at else None)
            # Until there are session scores: the score columns stay empty.
            row.speech = row.stability = None
        return render(request, "web/sessions.html", {
            "query": query,
            "status": status,
            "period": period,
            "rows": rows,
            # The filter menu (web/components/filter_menu.html), as on the Users page.
            "filter_groups": [
                {"name": "status", "label": "Status", "multiple": False,
                 "options": STATUS_OPTIONS, "selected": [status]},
                {"name": "period", "label": "Time", "multiple": False,
                 "options": PERIOD_OPTIONS, "selected": [period]},
            ],
            # Until the list is built: the numbers stay 0 and the search filters nothing.
            "sessions_this_week": 0,
            "upcoming_today": 0,
        })

    form = SessionCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": {
            name: [error["message"] for error in errors]
            for name, errors in form.errors.get_json_data().items()
        }}, status=400)
    data = form.cleaned_data
    try:
        session = create_session(
            trainer=request.user,
            speaker_id=data["speaker_id"],
            display=Session.Display.BOTH if data["stream_on_phone"] else Session.Display.WEB,
            scheduled_at=data["scheduled_at"] if data["start"] == "later" else None,
        )
    except ValidationError as error:
        # Field errors (scheduled_at from full_clean) come as a dict; the
        # others create_session raises are all about the speaker.
        errors = error.message_dict if hasattr(error, "error_dict") else {
            "speaker_id": error.messages}
        return JsonResponse({"errors": errors}, status=400)
    messages.success(
        request, f"Session with {session.speaker.user.get_full_name()} saved.")
    return JsonResponse({"id": session.id}, status=201)


@require_http_methods(["GET", "PATCH", "DELETE"])
@role_required(User.Role.ADMIN)
def session(request, session_id):
    if request.method == "GET":
        try:
            # With its talks, oldest first, without discarded ones (see get_session).
            session = get_session(user=request.user, session_id=session_id)
        except ValidationError:
            # Doesn't exist or isn't yours: the same 404 either way.
            raise Http404

        # The talks card: session.talks.all() is oldest first, without discarded ones.
        talks = list(session.talks.all())
        for number, row in enumerate(talks, start=1):
            row.number = number
            seconds = round(row.duration.total_seconds()) if row.duration else None
            row.length = f"{seconds // 60}:{seconds % 60:02d}" if seconds is not None else None
            result = getattr(row, "full_voice_result", None)
            row.speech = (round(result.voice_score)
                          if result is not None and result.voice_score is not None else None)
            # Until there is stability data.
            row.stability = None

        # The graphs show the latest talk with a full voice result; the eye in
        # the talks card switches to another one (web:talk, as JSON).
        latest = next((row for row in reversed(talks)
                       if getattr(row, "full_voice_result", None) is not None), None)
        talk = get_talk(user=request.user, talk_id=latest.id) if latest is not None else None
        # The header: how long it has run, start to end, or to now while it goes on.
        elapsed = None
        if session.started_at is not None:
            seconds = round(((session.ended_at or timezone.now()) - session.started_at).total_seconds())
            hours, rest = divmod(seconds, 3600)
            elapsed = (f"{hours}:{rest // 60:02d}:{rest % 60:02d}" if hours
                       else f"{rest // 60}:{rest % 60:02d}")
        # The same rule as start_talk(): live, and no talk recording or paused.
        can_start_talk = (session.status == Session.Status.LIVE and not any(
            row.status in (Talk.Status.RECORDING, Talk.Status.PAUSED) for row in talks))

        return render(request, "web/session.html", {
            "session": session,
            "talks": talks,
            "elapsed": elapsed,
            "can_start_talk": can_start_talk,
            "next_talk": len(talks) + 1,
            # talk (its id, number, started_at, length), voice_config,
            # stability_config, speech_score, stability_score
            **get_talk_graphs(talk),
        })

    # PATCH (the edit dialog) and DELETE (the confirm dialog) answer JSON, like
    # creating one: the success message waits as a toast for the reload.
    if request.method == "PATCH":
        # Django fills request.POST only for POST; the dialog sends the same
        # form fields in the PATCH body.
        form = SessionBaseForm(QueryDict(request.body))
        if not form.is_valid():
            return JsonResponse({"errors": {
                name: [error["message"] for error in errors]
                for name, errors in form.errors.get_json_data().items()
            }}, status=400)
        data = form.cleaned_data
        try:
            session = update_session(
                trainer=request.user,
                session_id=session_id,
                display=Session.Display.BOTH if data["stream_on_phone"] else Session.Display.WEB,
                # "Now" removes the schedule: it is started on the spot.
                scheduled_at=data["scheduled_at"] if data["start"] == "later" else None,
            )
        except ValidationError as error:
            if getattr(error, "code", None) == SESSION_NOT_YOURS:
                raise Http404
            # Field errors (scheduled_at from full_clean) come as a dict: 400;
            # a session that has started can't be changed any more: 409.
            if hasattr(error, "error_dict"):
                return JsonResponse({"errors": error.message_dict}, status=400)
            return JsonResponse({"errors": {"__all__": error.messages}}, status=409)
        messages.success(request, f"Session with {session.speaker.user.get_full_name()} saved.")
        return JsonResponse({"id": session.id})

    if request.method == "DELETE":
        try:
            session = delete_session(trainer=request.user, session_id=session_id)
        except ValidationError as error:
            if error.code == SESSION_NOT_YOURS:
                raise Http404
            # Not finished: only finished sessions can be deleted.
            return JsonResponse({"errors": {"__all__": error.messages}}, status=409)
        messages.success(
            request, f"Session with {session.speaker.user.get_full_name()} deleted. "
                     "It is under Discarded now.")
        return JsonResponse({"id": session.id})


@login_required
def talk_demo(request):
    """The screen while a talk is going on. Demo data only for now."""
    return render(request, "web/talk.html", {"voice_config": VOICE_CHART})
