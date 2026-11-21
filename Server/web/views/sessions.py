"""Session pages: the Sessions page (list for now empty) with creating a
session from the new session dialog, and the talk screen (talk.html, the
screen while a talk is going on, with no URL yet). The dialog's user search
is web:invite_suggestions with own=1 (web/views/users.py)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from accounts.models import User
from core.models import Session
from core.services.SessionsService import (
    SESSION_FILTERS,
    SESSION_PERIODS,
    create_session,
    get_sessions,
)

from ..decorators import role_required
from ..forms import SessionCreateForm

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
        rows = list(get_sessions(request.user.admin_profile, status, query, period))
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
        errors = error.message_dict if hasattr(error, "error_dict") else {"speaker_id": error.messages}
        return JsonResponse({"errors": errors}, status=400)
    messages.success(request, f"Session with {session.speaker.user.get_full_name()} saved.")
    return JsonResponse({"id": session.id}, status=201)


@login_required
def talk_demo(request):
    """The screen while a talk is going on. Demo data only for now."""
    return render(request, "web/talk.html", {"voice_config": VOICE_CHART})
