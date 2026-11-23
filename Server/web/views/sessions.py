"""Session pages: the Sessions page with creating a session from the new
session dialog, one session's page (and editing and deleting it), its
live screen (live.html) and the live screen's WebRTC connection
(session_connect, through live/client.py; live.js). The new session dialog's user
search is web:invite_suggestions with own=1 (web/views/users.py)."""

import json
import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse, JsonResponse, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.vary import vary_on_headers

from accounts.models import User
from core.models import File, Session, Talk
from core.services.FilesService import ALLOWED_TYPES
from core.services.GraphsService import get_talk_graphs
from core.services.SessionsService import (
    SESSION_FILTERS,
    SESSION_NOT_YOURS,
    SESSION_PERIODS,
    create_session,
    delete_session,
    end_session,
    get_session,
    get_sessions,
    start_session,
    update_session,
)
from core.services.TalksService import finish_talk, get_talk
from live.client import LiveClient, LiveError
from live.models import Connection

from ..decorators import role_required
from ..forms import SessionBaseForm, SessionCreateForm

logger = logging.getLogger(__name__)

# The live voice graph on the live screen's talk view (talk_content.html): pace
# (the solid line) and pitch variation (the dashed one, second_points) as
# scores from -10 to +10, with the optimal band from -5 to +5. Live: it shows
# the minute the newest score is in and moves on as the data gets there.
LIVE_VOICE_CHART = {
    "measure": "speech",
    "live": True,
    "x": {"min": 0, "interval": 10, "window": 60},
    "y": {"min": -10, "max": 10, "interval": 5},
    "target": {"low": -5, "high": 5},
    "points": [],
    "second_points": [],
}

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

@require_http_methods(["GET", "POST"])
@role_required(User.Role.ADMIN)
def session_list(request):
    """GET: the Sessions page: the head (numbers, search ?q= by the user's
    name or email, New session, which opens the new session dialog), the
    filters (?status=, see SESSION_FILTERS, default past; ?period=, see
    SESSION_PERIODS, default all; an unknown value falls back to the
    default) and the sessions table from get_sessions(), newest first.
    Above it the session cards: the live session (Reconnect), else the next
    two upcoming ones (Start).

    POST: create a session, from the new session dialog
    (new-session-dialog.js posts the form). 201 {"id": ..., "live_url": ...}:
    created; the message also waits as a toast for the next page (the live
    screen after Start, the reloaded Sessions page after Save). 400 {"errors": {field:
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
        trainer = request.user.admin_profile
        rows = list(get_sessions(trainer, status, query, period))
        # The cards above the table (session_card.html): the live session, to
        # reconnect to; without one the next two upcoming ones, the soonest
        # first, those without a time after them.
        live = (Session.objects.filter(trainer=trainer, status=Session.Status.LIVE)
                .select_related("speaker__user")
                .annotate(talk_count=Count("talks", filter=~Q(talks__status=Talk.Status.DISCARDED)))
                .first())
        upcoming = [] if live else list(
            Session.objects.filter(trainer=trainer, status=Session.Status.NOT_STARTED)
            .select_related("speaker__user")
            .order_by(F("scheduled_at").asc(nulls_last=True), "created_at")[:2])
        for row in rows:
            # Whole minutes from start to end; None until it has ended.
            row.minutes = (round((row.ended_at - row.started_at).total_seconds() / 60)
                           if row.started_at and row.ended_at else None)
            # Until there are session scores: the score columns stay empty.
            row.speech = row.stability = None
        return render(request, "web/sessions.html", {
            "live": live,
            "upcoming": upcoming,
            "now": timezone.now(),
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
    return JsonResponse({
        "id": session.id,
        "live_url": reverse("web:session_live", args=[session.id]),
    }, status=201)


@require_http_methods(["GET", "PATCH", "DELETE"])
@role_required(User.Role.ADMIN)
@vary_on_headers("Accept")
def session(request, session_id):
    """GET: the session as JSON, for the page's script (session.js) to draw:
    {"session": {"id", "status", "started_at", "ended_at"}, "talks": [{"id",
    "number", "status", "started_at", "duration" (seconds), "speech",
    "stability", "url" (its graphs, web:talk), "finish_url" (End talk,
    web:talk_finish), "paused_seconds" and "paused_at" (the ended pauses'
    seconds and the start of the one going on, for a talk going on; else 0
    and null)}], and the graphs of its latest
    talk with a full voice result (a talk still processing has none):
    "talk", "voice_config", "stability_config", "speech_score",
    "stability_score", as get_talk_graphs() gives them. The talks are oldest
    first, without discarded ones. With Accept: application/json that is the
    answer; else the session page, with the same JSON in it (json_script).
    Vary: Accept, so a cache keeps the two apart.

    PATCH: change it (the edit dialog). DELETE: delete it (the confirm
    dialog). Doesn't exist or isn't yours: 404."""
    if request.method == "GET":
        try:
            # With its talks, oldest first, without discarded ones (see get_session).
            session = get_session(user=request.user, session_id=session_id)
        except ValidationError:
            # Doesn't exist or isn't yours: the same 404 either way.
            raise Http404

        talks, latest = [], None
        for number, row in enumerate(session.talks.all(), start=1):
            result = getattr(row, "full_voice_result", None)
            if result is not None:
                latest = row
            # For the talk going on, its pauses (the live screen's talk clock):
            # the seconds of the ended ones, and when the one going on began.
            paused_seconds, paused_at = 0, None
            if row.status in (Talk.Status.RECORDING, Talk.Status.PAUSED):
                for pause in row.pauses.all():
                    if pause.resumed_at is None:
                        paused_at = pause.paused_at
                    else:
                        paused_seconds += (pause.resumed_at - pause.paused_at).total_seconds()
            talks.append({
                "id": row.id,
                "number": number,
                "status": row.status,
                "started_at": row.started_at,
                "duration": row.duration.total_seconds() if row.duration else None,
                "speech": result.voice_score if result is not None else None,
                "stability": None,  # until there is stability data
                "url": reverse("web:talk", args=[row.id]),
                "finish_url": reverse("web:talk_finish", args=[row.id]),
                "paused_seconds": paused_seconds,
                "paused_at": paused_at,
            })
        talk = get_talk(user=request.user, talk_id=latest.id) if latest is not None else None
        data = {
            "session": {
                "id": session.id,
                "status": session.status,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
            },
            "talks": talks,
            **get_talk_graphs(talk),
        }
        if request.get_preferred_type(["text/html", "application/json"]) == "application/json":
            return JsonResponse(data)
        return render(request, "web/session.html", {"session": session, "data": data})

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


@require_http_methods(["GET", "POST"])
@role_required(User.Role.ADMIN)
def session_live(request, session_id):
    """GET: the live screen of a live session: its header and its WebRTC
    connection, which live.js sets up by itself (web:session_connect). A
    session that isn't live: its session page.

    POST: start the session (the play button, Start in the new session
    dialog and in the session header), then GET here. If it can't start
    (already live, or the speaker has another live session) the GET decides:
    the live screen when it is live, else the session page with why.
    Doesn't exist or isn't yours: 404."""
    if request.method == "POST":
        try:
            start_session(trainer=request.user, session_id=session_id)
        except ValidationError as error:
            if error.code == SESSION_NOT_YOURS:
                raise Http404
            if not Session.objects.filter(pk=session_id, status=Session.Status.LIVE).exists():
                messages.error(request, error.messages[0])
        return redirect("web:session_live", session_id=session_id)

    try:
        session = get_session(user=request.user, session_id=session_id)
    except ValidationError:
        raise Http404
    if session.status != Session.Status.LIVE:
        return redirect("web:session", session_id=session.id)
    return render(request, "web/live.html", {"session": session, "live_voice_config": LIVE_VOICE_CHART})


@require_http_methods(["GET", "POST"])
@role_required(User.Role.ADMIN)
def session_connect(request, session_id):
    """The trainer's WebRTC connection to the live process, for the live
    screen (live.js), through the live client (live/client.py). JSON, both
    ways; the session must be yours (else 404) and live (else 409).

    GET: a new connection and its offer (an older one of this session is
    replaced), with the ICE servers for the browser: {"sdp", "ice_servers",
    "ice_transport_policy"}, from LiveClient.offer(). The browser answers
    within the live process's offer timeout (30 s).

    POST {"sdp"}: the browser's answer to that offer. 204: passed on; the
    connection then comes up by itself (ICE and DTLS).

    Errors are {"errors": {"__all__": [...]}} with "code": 400 a bad body,
    404 and 409 the live process's own (no offer waiting, answered already,
    replaced by a newer one), 503 when it can't be reached."""
    try:
        session = get_session(user=request.user, session_id=session_id)
    except ValidationError:
        raise Http404
    if session.status != Session.Status.LIVE:
        return JsonResponse({"code": "not_live", "errors": {"__all__": ["This session isn't live."]}},
                            status=409)

    client = LiveClient()
    kind = Connection.Kind.TRAINER_AUDIO
    try:
        if request.method == "GET":
            return JsonResponse(client.offer(session.id, request.user.id, kind))

        try:
            answer = json.loads(request.body)["sdp"]
        except (ValueError, KeyError, TypeError):
            answer = None
        if not isinstance(answer, str) or not answer.strip():
            return JsonResponse({"code": "invalid_body", "errors": {"__all__": ["Send the answer as {\"sdp\": ...}."]}},
                                status=400)
        client.answer(session.id, request.user.id, kind, answer)
        return HttpResponse(status=204)
    except LiveError as error:
        # The live process's "nothing waiting" and "wrong state" go to the
        # browser as they are (it starts over); anything else is ours.
        if error.status in (404, 409):
            return JsonResponse({"code": error.code, "errors": {"__all__": [error.detail]}},
                                status=error.status)
        logger.warning("Live process call failed for session %s: %s (%s)", session.id, error.detail, error.code)
        return JsonResponse({"code": "live_unavailable", "errors": {"__all__": [
            "The live connection isn't available right now."]}}, status=503)


@require_http_methods(["POST"])
@role_required(User.Role.ADMIN)
def session_finish(request, session_id):
    """POST: Finish session (the confirm dialog, from the session header or the
    talk header): End talk for a talk still going on, then the session, so a
    talk finished this way goes the same way as with the End talk button. It
    takes the same optional "audio" (the browser's recording of that talk).

    1. the checks, before anything changes: 400 for a file that isn't audio
       we take or is empty; 404 for a session that doesn't exist or isn't
       yours; 409 for one that isn't live, or for a file with no talk going on;
    2. End talk, as talk_finish does it: the live process stops the talk's
       recording (its file closed, complete), then finish_talk() (-> PROCESSING),
       which stores the browser's file, or else the live process's recording;
    3. the session: the live process closes its connections (and its reconnect
       timer), then end_session() (-> FINISHED). end_session still closes a
       talk left open itself, but here there is none left.

    200 {"id"}, with a toast for the reload. A failing live process only goes
    to the log: the talk and the session are finished anyway."""
    audio = request.FILES.get("audio")
    if audio is not None and (audio.content_type not in ALLOWED_TYPES[File.Kind.AUDIO] or not audio.size):
        return JsonResponse({"errors": {"audio": ["Send the talk's recording as WebM, Ogg, MP4 or WAV audio."]}},
                            status=400)
    try:
        session = get_session(user=request.user, session_id=session_id)
    except ValidationError:
        raise Http404
    if session.status != Session.Status.LIVE:
        return JsonResponse({"errors": {"__all__": ["This session isn't live."]}}, status=409)
    # From get_session's prefetch: the talks without discarded ones. At most one.
    open_talks = [talk.id for talk in session.talks.all()
                  if talk.status in (Talk.Status.RECORDING, Talk.Status.PAUSED)]
    if audio is not None and not open_talks:
        return JsonResponse({"errors": {"__all__": ["There's no talk going on for this recording."]}}, status=409)

    client = LiveClient()
    # End talk.
    for talk_id in open_talks:
        recording = None
        try:
            recording = client.stop_recording(talk_id)
        except LiveError as error:
            # 404 not_recording: nothing was recording it (a live restart).
            if error.status != 404:
                logger.warning("Stopping the recording of talk %s failed: %s (%s)",
                               talk_id, error.detail, error.code)
        try:
            finish_talk(trainer=request.user, talk_id=talk_id, audio=audio, recording=recording)
        except ValidationError:
            # Ended in the moment since the check: end_session closes what is left.
            pass

    # The session.
    try:
        client.close_session(session.id)
    except LiveError as error:
        logger.warning("Closing the connections of session %s failed: %s (%s)",
                       session.id, error.detail, error.code)

    try:
        session = end_session(trainer=request.user, session_id=session_id)
    except ValidationError as error:
        # Ended in the moment since the check (the reconnect timeout).
        return JsonResponse({"errors": {"__all__": error.messages}}, status=409)
    messages.success(request, f"Session with {session.speaker.user.get_full_name()} finished.")
    return JsonResponse({"id": session.id})
