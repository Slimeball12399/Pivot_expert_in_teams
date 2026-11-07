"""Trainer invitations, the speaker's side (tag "invites").

Trainers send and cancel invitations on the web. In the app a speaker sees
the invitations sent to their verified email and accepts or declines them.
The rules live in accounts.services.invites; these views only turn the
results into HTTP responses.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.services import invites as invite_services

from ..decorators import role_required
from ..exceptions import CodedError
from ..serializers import (
    CodedErrorSerializer,
    DetailSerializer,
    InviteAcceptedSerializer,
    InviteSerializer,
)

TAGS = ["invites"]
INVITE_ACCEPTED = "Invitation accepted. You're now training with this trainer."
INVITE_DECLINED = "Invitation declined."


@extend_schema_view(get=extend_schema(tags=TAGS, responses=InviteSerializer(many=True)))
class InviteListView(APIView):
    """GET /api/invites/ - the speaker's open invitations, newest first."""

    permission_classes = [IsAuthenticated]

    @role_required(User.Role.SPEAKER)
    def get(self, request):
        invites = invite_services.pending_invites_for(request.user)
        return Response(InviteSerializer(invites, many=True).data)


@extend_schema_view(post=extend_schema(
    tags=TAGS, request=None,
    responses={200: InviteAcceptedSerializer, 404: CodedErrorSerializer},
))
class InviteAcceptView(APIView):
    """POST /api/invites/<id>/accept/ - accept an invitation. No body.

    The speaker moves to the inviting trainer; a trainer they already had is
    replaced (the app asks for confirmation before calling this), and their
    other open invitations are withdrawn. Returns the new trainer and the
    previous one (null when there was none). An unknown invitation, someone
    else's, or one that is no longer open: 404 {"code": "invite_not_found"}.
    """

    permission_classes = [IsAuthenticated]

    @role_required(User.Role.SPEAKER)
    def post(self, request, invite_id):
        try:
            invite, previous_trainer = invite_services.accept_invite(request.user, invite_id)
        except DjangoValidationError as e:
            raise CodedError(e.messages[0], e.code, status_code=404)
        return Response(InviteAcceptedSerializer({
            "detail": INVITE_ACCEPTED,
            "trainer": invite.invited_by,
            "previous_trainer": previous_trainer,
        }).data)


@extend_schema_view(post=extend_schema(
    tags=TAGS, request=None,
    responses={200: DetailSerializer, 404: CodedErrorSerializer},
))
class InviteDeclineView(APIView):
    """POST /api/invites/<id>/decline/ - decline an invitation. No body.

    Errors like accept: 404 {"code": "invite_not_found"}.
    """

    permission_classes = [IsAuthenticated]

    @role_required(User.Role.SPEAKER)
    def post(self, request, invite_id):
        try:
            invite_services.revoke_invite(request.user, invite_id)
        except DjangoValidationError as e:
            raise CodedError(e.messages[0], e.code, status_code=404)
        return Response({"detail": INVITE_DECLINED})
