"""Session endpoints (tag "sessions")."""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from core.services import SessionsService as session_services
from core.services.SessionsService import INVALID_TRANSITION, SESSION_NOT_YOURS

from ..decorators import role_required
from ..exceptions import CodedError
from ..serializers.common import CodedErrorSerializer
from ..serializers.sessions import (
    SessionCreateSerializer,
    SessionDetailSerializer,
    SessionListQuerySerializer,
    SessionSerializer,
    SessionUpdateSerializer,
)

TAGS = ["sessions"]
# HTTP status for each error code from SessionsService; any other code is a 400.
ERROR_STATUS = {SESSION_NOT_YOURS: 404, INVALID_TRANSITION: 409}


def api_error(error):
    if hasattr(error, "error_dict"):
        return ValidationError(error.message_dict)
    return CodedError(error.messages[0], error.code,
                      status_code=ERROR_STATUS.get(error.code, 400))


@extend_schema_view(
    get=extend_schema(
        tags=TAGS, parameters=[SessionListQuerySerializer],
        responses={200: SessionSerializer(many=True), 400: CodedErrorSerializer}),
    post=extend_schema(
        tags=TAGS, request=SessionCreateSerializer,
        responses={201: SessionSerializer, 400: CodedErrorSerializer}),
)
class SessionListView(APIView):
    permission_classes = [IsAuthenticated]

    @role_required(User.Role.ADMIN, User.Role.SPEAKER)
    def get(self, request):
        query = SessionListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data
        try:
            sessions = session_services.list_sessions(
                user=request.user, statuses=filters.get("status"),
                speaker_id=filters.get("speaker_id"),
                limit=filters["limit"], offset=filters["offset"])
        except DjangoValidationError as e:
            raise api_error(e)
        return Response(SessionSerializer(sessions, many=True).data)

    @role_required(User.Role.ADMIN)
    def post(self, request):
        data = SessionCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            session = session_services.create_session(trainer=request.user, **data.validated_data)
        except DjangoValidationError as e:
            raise api_error(e)
        return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=TAGS, responses={200: SessionDetailSerializer, 404: CodedErrorSerializer}),
    patch=extend_schema(
        tags=TAGS, request=SessionUpdateSerializer,
        responses={200: SessionDetailSerializer, 400: CodedErrorSerializer,
                   404: CodedErrorSerializer, 409: CodedErrorSerializer}),
    delete=extend_schema(
        tags=TAGS, request=None,
        responses={200: SessionDetailSerializer, 404: CodedErrorSerializer,
                   409: CodedErrorSerializer}),
)
class SessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @role_required(User.Role.ADMIN, User.Role.SPEAKER)
    def get(self, request, session_id):
        try:
            session = session_services.get_session(user=request.user, session_id=session_id)
        except DjangoValidationError as e:
            raise api_error(e)
        return Response(SessionDetailSerializer(session).data)

    @role_required(User.Role.ADMIN)
    def patch(self, request, session_id):
        data = SessionUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        try:
            session = session_services.update_session(
                trainer=request.user, session_id=session_id, **data.validated_data)
        except DjangoValidationError as e:
            raise api_error(e)
        return Response(SessionDetailSerializer(session).data)

    @role_required(User.Role.ADMIN)
    def delete(self, request, session_id):
        try:
            session = session_services.cancel_session(trainer=request.user, session_id=session_id)
        except DjangoValidationError as e:
            raise api_error(e)
        return Response(SessionDetailSerializer(session).data)
