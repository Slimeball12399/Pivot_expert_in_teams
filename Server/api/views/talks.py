"""Talk endpoints (tag "talks"). A session's talks in short form come with
GET /api/sessions/<id>/; here one talk in full, discarding it and ending it.
Starting, pausing and resuming a talk go over the WebRTC data channel."""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from core.services import TalksService as talk_services

from ..decorators import role_required
from ..exceptions import CodedError
from ..serializers.common import CodedErrorSerializer
from ..serializers.sessions import TalkDetailSerializer, TalkSummarySerializer

TAGS = ["talks"]


@extend_schema_view(
    get=extend_schema(
        tags=TAGS, responses={200: TalkDetailSerializer, 404: CodedErrorSerializer}),
    delete=extend_schema(
        tags=TAGS, request=None,
        responses={200: TalkSummarySerializer, 404: CodedErrorSerializer,
                   409: CodedErrorSerializer}),
)
class TalkDetailView(APIView):
    """GET /api/talks/<id>/ - a talk with its full voice result (null until
    processed) and its analysis windows, in time order.

    DELETE /api/talks/<id>/ - an admin discards a talk. The talk stays, with
    status DISCARDED, and its audio is deleted. Already discarded: 409
    {"code": "invalid_transition"}.

    Someone else's talk, or one that doesn't exist: 404 {"code": "talk_not_yours"}.
    """

    permission_classes = [IsAuthenticated]

    @role_required(User.Role.ADMIN, User.Role.SPEAKER)
    def get(self, request, talk_id):
        try:
            talk = talk_services.get_talk(user=request.user, talk_id=talk_id)
        except DjangoValidationError as e:
            raise CodedError(e.messages[0], e.code, status_code=404)
        return Response(TalkDetailSerializer(talk).data)

    @role_required(User.Role.ADMIN)
    def delete(self, request, talk_id):
        # Once the WebRTC peer exists, discarding an open talk also has to tell
        # it to stop recording, like ending one.
        try:
            talk = talk_services.discard_talk(trainer=request.user, talk_id=talk_id)
        except DjangoValidationError as e:
            status_code = 404 if e.code == talk_services.TALK_NOT_YOURS else 409
            raise CodedError(e.messages[0], e.code, status_code=status_code)
        return Response(TalkSummarySerializer(talk).data)


@extend_schema_view(post=extend_schema(tags=TAGS, request=None, responses=None))
class TalkEndView(APIView):
    """POST /api/talks/<id>/end/ - end a talk, optionally with its exact WAV.
    Not built yet."""

    permission_classes = [IsAuthenticated]

    @role_required(User.Role.ADMIN)
    def post(self, request, talk_id):
        raise NotImplementedError("Ending a talk over HTTP isn't built yet.")
