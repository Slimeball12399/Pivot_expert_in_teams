"""The live process's internal API: what Django (the web process) calls to set
up a trainer's connection, close a session's connections and stop a talk's
recording. Async views, on the same event loop as the connections they work
with (live/runtime.py).

Never for browsers: it is only reachable inside Docker's network (or on
localhost in development), and every request needs LIVE_INTERNAL_TOKEN in the
X-Live-Token header. Django has already checked who the user is and that they
may do it; this only does it.

  POST /offer/                          {session_id, user_id, kind}       -> {"sdp"}
  POST /answer/                         {session_id, user_id, kind, sdp}  -> 204
  POST /sessions/<id>/close/                                              -> {"closed": true/false}
  POST /talks/<id>/stop-recording/                                        -> {"talk_id", "path"}

Errors: {"code", "detail"}, 400 for a bad body (with "errors" per field, from
the serializers in live/serializers.py), 401 without the token, 404
for nothing found (or not that user's, or a malformed id in the URL), 409 for
the wrong state. "path" is the recording's PCM, relative to FILES_DIR (the
folder both processes share, mounted in different places on the host and in
Docker).
"""

import hmac
import json
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from rest_framework import serializers

from live import runtime
from live.serializers import AnswerSerializer, ConnectionBaseSerializer
from live.Services.ConnectionService import (
    CONNECTION_NOT_FOUND,
    CONNECTION_REPLACED,
    NOT_WAITING_FOR_ANSWER,
)

# Error codes of this API itself, next to the services' ones.
INVALID_BODY = "invalid_body"
UNAUTHORIZED = "unauthorized"
NOT_RECORDING = "not_recording"

# The HTTP status of each error code; anything else is a conflict (409).
STATUS = {
    INVALID_BODY: 400,
    CONNECTION_NOT_FOUND: 404,
    NOT_RECORDING: 404,
    NOT_WAITING_FOR_ANSWER: 409,
    CONNECTION_REPLACED: 409,
}


def internal_only(view):
    """Every internal view: the token first (compared in constant time, so its
    value can't be guessed from how long a refusal takes), then the view,
    with a serializer's errors (a bad body) and a service's ValidationError
    turned into {"code", "detail"}."""
    @wraps(view)
    async def wrapper(request, *args, **kwargs):
        if not hmac.compare_digest(request.headers.get("X-Live-Token", ""), settings.LIVE_INTERNAL_TOKEN):
            return JsonResponse({"code": UNAUTHORIZED, "detail": "Missing or wrong X-Live-Token."},
                                status=401)
        try:
            return await view(request, *args, **kwargs)
        except serializers.ValidationError as error:
            return JsonResponse({"code": INVALID_BODY, "detail": "The request body doesn't fit.",
                                 "errors": error.detail}, status=400)
        except ValidationError as error:
            return JsonResponse({"code": error.code, "detail": error.messages[0]},
                                status=STATUS.get(error.code, 409))
    return wrapper


def read_body(request, serializer_class) -> dict:
    """The JSON body, checked by the serializer (live/serializers.py): its
    validated data. Raises the serializer's ValidationError (400, with the
    field errors) for anything that isn't JSON or doesn't fit."""
    try:
        data = json.loads(request.body)
    except ValueError as error:
        raise serializers.ValidationError({"body": ["Not JSON."]}) from error
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@require_POST
@internal_only
async def offer(request):
    """A new peer connection for the session and kind (replacing an older
    one), and its offer for the browser."""
    data = read_body(request, ConnectionBaseSerializer)
    sdp = await runtime.CONNECTIONS.create_offer(data["session_id"], data["user_id"], data["kind"])
    return JsonResponse({"sdp": sdp})


@require_POST
@internal_only
async def answer(request):
    """The browser's answer to the offer of that session, kind and user."""
    data = read_body(request, AnswerSerializer)
    await runtime.CONNECTIONS.accept_answer(data["session_id"], data["user_id"], data["kind"], data["sdp"])
    return HttpResponse(status=204)


@require_POST
@internal_only
async def close_session(request, session_id):
    """Closes the session's connections (it ended or was aborted). Fine when
    there are none: "closed" says whether there were."""
    closed = await runtime.CONNECTIONS.close_session(session_id)
    return JsonResponse({"closed": closed})


@require_POST
@internal_only
async def stop_recording(request, talk_id):
    """Stops the talk's recording (it was finished or discarded) and says
    where its PCM is, relative to FILES_DIR. 404 when that talk isn't
    recording: never started here, stopped already, or lost with a restart
    (then its file is still there, under recordings/<talk id>.pcm)."""
    recording = runtime.AUDIO.finish_recording(talk_id)
    if recording is None:
        raise ValidationError("This talk isn't recording.", code=NOT_RECORDING)
    return JsonResponse({
        "talk_id": str(recording.talk_id),
        "path": recording.path.relative_to(runtime.AUDIO.recordings_dir.parent).as_posix(),
    })
