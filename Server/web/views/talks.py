"""Talks: one talk's graphs as JSON, for the session page's talks card. The
talk page (HTML, the talk that is going on) comes later at talk/."""

from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

from accounts.models import User
from core.services.GraphsService import get_talk_graphs
from core.services.TalksService import get_talk

from ..decorators import role_required


@require_GET
@role_required(User.Role.ADMIN)
def talk(request, talk_id):
    """GET: the talk's graphs, as get_talk_graphs() gives them: {"talk": {"id",
    "number", "started_at", "length"}, "voice_config", "stability_config",
    "speech_score", "stability_score"}. session.js redraws the session page's
    graphs with it. 404 for a talk that doesn't exist or isn't yours (the
    same either way)."""
    try:
        # With its partial voice results in time order.
        talk = get_talk(user=request.user, talk_id=talk_id)
    except ValidationError:
        raise Http404
    return JsonResponse(get_talk_graphs(talk))
