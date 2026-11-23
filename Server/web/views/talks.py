"""Talks: one talk's graphs as JSON, for the session page's talks card, and
ending the talk going on (End talk, on the live screen)."""

import logging

from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.models import User
from core.models import File, Talk
from core.services.FilesService import ALLOWED_TYPES
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
    """POST: End talk (live.js), optionally with the browser's recording of
    the talk in "audio" (multipart; WebM, Ogg or MP4). In this order: the
    checks (400 for a file that isn't audio we take or is empty; 404 for a
    talk that doesn't exist or isn't yours; 409 for one that isn't recording
    or paused); the live process stops its recording (the file closed,
    complete); then finish_talk() (-> PROCESSING, with its duration), which
    stores the browser's file, or else the live process's recording as a WAV.
    200 {"id"}. A failing live process only goes to the log: the talk is
    finished anyway (with the browser's file if there is one)."""
    audio = request.FILES.get("audio")
    if audio is not None and (audio.content_type not in ALLOWED_TYPES[File.Kind.AUDIO] or not audio.size):
        return JsonResponse({"errors": {"audio": ["Send the talk's recording as WebM, Ogg, MP4 or WAV audio."]}},
                            status=400)
    try:
        talk = get_talk(user=request.user, talk_id=talk_id)
    except ValidationError:
        raise Http404
    if talk.status not in (Talk.Status.RECORDING, Talk.Status.PAUSED):
        return JsonResponse({"errors": {"__all__": [
            f"Only a recording or paused talk can be ended; this one is {talk.get_status_display().lower()}."]}},
            status=409)
    recording = None
    try:
        recording = LiveClient().stop_recording(talk.id)
    except LiveError as error:
        # 404 not_recording: nothing was recording it (a live restart).
        if error.status != 404:
            logger.warning("Stopping the recording of talk %s failed: %s (%s)", talk.id, error.detail, error.code)
    try:
        talk = finish_talk(trainer=request.user, talk_id=talk.id, audio=audio, recording=recording)
    except ValidationError as error:
        # Ended in the moment since the check.
        return JsonResponse({"errors": {"__all__": error.messages}}, status=409)
    return JsonResponse({"id": talk.id})
