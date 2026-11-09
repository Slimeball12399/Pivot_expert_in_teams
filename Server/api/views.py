from django.db import connection
from drf_spectacular.utils import (
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
)
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from .serializers import (
    ME_SERIALIZERS,
    ME_UPDATE_SERIALIZERS,
    HealthSerializer,
    RegisteredUserSerializer,
    SpeakerRegistrationSerializer,
    me_data,
)


# auth=[]: no lock icon in Swagger UI (public endpoint).
@extend_schema(tags=["system"], responses=HealthSerializer, auth=[])
@api_view(["GET"])
@permission_classes([AllowAny])  # public on purpose: used to check the server is up
@authentication_classes([])  # never reads a token, so a bad one can't cause a 401
def health(request):
    """GET /api/health/ - is the server up and can it reach the database?"""
    try:
        connection.ensure_connection()
        db = "ok"
    except Exception:
        db = "down"
    return Response({"status": "ok", "database": db})


@extend_schema_view(post=extend_schema(
    tags=["auth"],
    request=SpeakerRegistrationSerializer,
    responses={201: RegisteredUserSerializer},
    auth=[],  # no lock icon in Swagger UI (public endpoint)
))
class RegisterView(CreateAPIView):
    """POST /api/auth/register/ - create a speaker account. Open to everyone."""

    serializer_class = SpeakerRegistrationSerializer
    permission_classes = [AllowAny]
    # Never read a token here: AllowAny skips the permission check, but an
    # expired or invalid "Authorization: Bearer" header would still give a 401.
    authentication_classes = []


# JWT auth for the mobile app. Simple JWT's own views, subclassed to give
# them our names and group them under "auth" in the API docs. Login and
# refresh are public; logout needs the user to be logged in.


@extend_schema_view(post=extend_schema(tags=["auth"]))
class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ - email + password in, access + refresh tokens out.

    Any role can log in; endpoints check the role themselves (api.decorators.role_required).
    """


@extend_schema_view(post=extend_schema(tags=["auth"]))
class RefreshView(TokenRefreshView):
    """POST /api/auth/refresh/ - refresh token in, new access + refresh tokens out.

    The refresh token sent in is blacklisted, so it works only once.
    """


@extend_schema_view(post=extend_schema(tags=["auth"]))
class LogoutView(TokenBlacklistView):
    """POST /api/auth/logout/ - blacklist the refresh token sent in the body.

    Needs the user to be logged in (Authorization: Bearer <access token>).
    The access token isn't revoked; it expires on its own
    (ACCESS_TOKEN_LIFETIME), so the app deletes both tokens.
    """

    # Simple JWT's views turn authentication off; logout turns it back on.
    authentication_classes = api_settings.DEFAULT_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]


# In the API docs: the body of /api/me/ depends on "role".
ME_RESPONSE = PolymorphicProxySerializer(
    component_name="Me",
    serializers=ME_SERIALIZERS,
    resource_type_field_name="role",
)
# The request has no "role" field (the server knows it), so the docs list
# both shapes as alternatives: the admin one or the speaker one.
ME_UPDATE_REQUEST = PolymorphicProxySerializer(
    component_name="MeUpdate",
    serializers=list(ME_UPDATE_SERIALIZERS.values()),
    resource_type_field_name=None,
)


@extend_schema_view(
    get=extend_schema(tags=["auth"], responses=ME_RESPONSE),
    patch=extend_schema(
        tags=["auth"], request=ME_UPDATE_REQUEST, responses=ME_RESPONSE),
)
class MeView(APIView):
    """GET /api/me/ - the logged-in user and their profile (admin or speaker).
    PATCH /api/me/ - change some of it. Any logged-in user."""

    # Also the project default; kept so the view says it.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(me_data(request.user))

    def patch(self, request):
        # Speakers can also send "profile"; admins only their own details.
        serializer_class = ME_UPDATE_SERIALIZERS[request.user.role]
        serializer = serializer_class(
            request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(me_data(user))
