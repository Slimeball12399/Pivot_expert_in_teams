"""Talks: one talk's graphs as JSON, for the session page's talks card, and
ending the talk going on (End talk, on the live screen)."""

import logging

from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.models import User
from core.models import Talk
from core.services.GraphsService import get_talk_graphs
from core.services.TalksService import finish_talk, get_talk
from live.client import LiveClient, LiveError

from ..decorators import role_required

logger = logging.getLogger(__name__)


@require_GET
@role_required(User.Role.ADMIN)
def talk(request, talk_id):
    """GET: the talk's graphs, as get_talk_graphs() gives them: {"talk": {"id",
    "number", "started_at", "length"}, "voice_config", "stability_config",
    "speech_score", "stability_score"}, the same keys as the graphs in the
    session's JSON (web:session). session.js shows it with showTalk(). 404 for a talk that doesn't exist or isn't yours (the
    same either way)."""
    try:
        # With its partial voice results in time order.
        talk = get_talk(user=request.user, talk_id=talk_id)
    except ValidationError:
        raise Http404
    return JsonResponse(get_talk_graphs(talk))


@require_POST
@role_required(User.Role.ADMIN)
def talk_finish(request, talk_id):
    """POST: End talk (live.js), in this order: the checks (404 for a talk
    that doesn't exist or isn't yours, 409 for one that isn't recording or
    paused); the live process stops its recording (the file closed,
    complete); then finish_talk() (-> PROCESSING, with its duration), last
    because it is where the finished recording will be uploaded. 200 {"id"}.
    A failing live process only goes to the log: the talk is finished anyway
    (its file is then closed with the session or the reconnect timeout)."""
    try:
        talk = get_talk(user=request.user, talk_id=talk_id)
    except ValidationError:
        raise Http404
    if talk.status not in (Talk.Status.RECORDING, Talk.Status.PAUSED):
        return JsonResponse({"errors": {"__all__": [
            f"Only a recording or paused talk can be ended; this one is {talk.get_status_display().lower()}."]}},
            status=409)
    try:
        LiveClient().stop_recording(talk.id)
    except LiveError as error:
        # 404 not_recording: nothing was recording it (a live restart).
        if error.status != 404:
            logger.warning("Stopping the recording of talk %s failed: %s (%s)", talk.id, error.detail, error.code)
    try:
        talk = finish_talk(trainer=request.user, talk_id=talk.id)
    except ValidationError as error:
        # Ended in the moment since the check.
        return JsonResponse({"errors": {"__all__": error.messages}}, status=409)
    return JsonResponse({"id": talk.id})
