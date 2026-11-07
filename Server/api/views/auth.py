"""Account endpoints for the mobile app (tag "auth"): register, login,
tokens, email verification, password reset and the user's own profile."""

from django.contrib.auth.models import update_last_login
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import (
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
)
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from accounts.services import accounts as account_services

from ..exceptions import CodedError
from ..serializers import (
    ME_SERIALIZERS,
    ME_UPDATE_SERIALIZERS,
    CodedErrorSerializer,
    DetailSerializer,
    EmailCodeSerializer,
    EmailSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetTokenSerializer,
    RegisteredUserSerializer,
    SpeakerRegistrationSerializer,
    TokenPairSerializer,
    me_data,
)


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


# Auth for the mobile app. The rules live in accounts.services; these views
# parse the input (serializers), call the service and turn its result into
# an HTTP response: tokens, a message, or {"detail", "code"} with a status.
# Refresh and logout are Simple JWT's own views (only tokens, no rules).


class PublicAPIView(APIView):
    """No login needed, and a stale "Authorization: Bearer" header is ignored."""

    permission_classes = [AllowAny]
    authentication_classes = []


PUBLIC = {"tags": ["auth"], "auth": []}  # no lock icon in Swagger UI

SENT_IF_EXISTS = "If that account exists and needs a code, we sent one."
PASSWORD_CHANGED = "Your password is changed. Log in with your new password."
EMAIL_VERIFIED = "Your email is verified. Log in to continue."


@extend_schema_view(post=extend_schema(
    **PUBLIC, request=LoginSerializer,
    responses={200: TokenPairSerializer, 401: CodedErrorSerializer, 403: CodedErrorSerializer},
))
class LoginView(PublicAPIView):
    """POST /api/auth/login/ - email + password in, access + refresh tokens out.

    Any role can log in; endpoints check the role themselves (api.decorators.role_required).
    Wrong email or password: 401 {"code": "invalid_login"}. Right password but
    unverified email: 403 {"code": "email_not_verified"}, and a new code is
    emailed; the app then opens the code screen.
    """

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = account_services.login_user(request, **serializer.validated_data)
        except DjangoValidationError as e:
            status_code = 403 if e.code == account_services.EMAIL_NOT_VERIFIED else 401
            raise CodedError(e.messages[0], e.code, status_code=status_code)
        if jwt_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)
        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh)})


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


# Email verification and password reset. Public, like login: the user has no
# tokens yet.


@extend_schema_view(
    post=extend_schema(**PUBLIC, request=EmailSerializer, responses=DetailSerializer),
    put=extend_schema(
        **PUBLIC, request=EmailCodeSerializer,
        responses={200: DetailSerializer, 400: CodedErrorSerializer},
    ),
)
class VerifyEmailView(PublicAPIView):
    """/api/auth/verify-email/ - the email verification code.

    POST {email}: send a new code (the "send a new code" button). Always 200
    with the same message, so it doesn't reveal which emails have accounts.
    Inside the 60-second cooldown nothing is sent; the last code still works.

    PUT {email, code}: mark the email verified. Returns no tokens, so a stolen
    code can't log anyone in: the app then calls login again with the email
    and password it kept in memory from the register or login screen. Any
    wrong, expired or used code (or too many attempts): 400 {"code": "invalid_code"}.
    """

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account_services.resend_verification_code(serializer.validated_data["email"])
        return Response({"detail": SENT_IF_EXISTS})

    def put(self, request):
        serializer = EmailCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            account_services.verify_email(**serializer.validated_data)
        except DjangoValidationError as e:
            raise CodedError(e.messages[0], e.code)
        return Response({"detail": EMAIL_VERIFIED})


@extend_schema_view(post=extend_schema(
    **PUBLIC, request=EmailSerializer, responses=DetailSerializer))
class PasswordResetRequestView(PublicAPIView):
    """POST /api/auth/password-reset/ - email in, a reset code out by email.

    Always 200 with the same message, like resend. Also the "send a new code"
    button on the reset code screen.
    """

    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account_services.request_password_reset(serializer.validated_data["email"])
        return Response({"detail": SENT_IF_EXISTS})


@extend_schema_view(post=extend_schema(
    **PUBLIC, request=EmailCodeSerializer,
    responses={200: PasswordResetTokenSerializer, 400: CodedErrorSerializer},
))
class PasswordResetVerifyView(PublicAPIView):
    """POST /api/auth/password-reset/verify/ - email + code in, uid + reset_token out.

    The app keeps both in memory for the new password screen. The token works
    for PASSWORD_RESET_TIMEOUT (10 minutes) and only until the password changes.
    """

    def post(self, request):
        serializer = EmailCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            uid, token = account_services.verify_password_reset_code(**serializer.validated_data)
        except DjangoValidationError as e:
            raise CodedError(e.messages[0], e.code)
        return Response({"uid": uid, "reset_token": token})


@extend_schema_view(put=extend_schema(
    **PUBLIC, request=PasswordResetConfirmSerializer,
    responses={200: DetailSerializer, 400: CodedErrorSerializer},
))
class PasswordResetConfirmView(PublicAPIView):
    """PUT /api/auth/password-reset/confirm/ - uid + reset_token + new_password in.

    Sets the password and logs the app out on every device. Returns no tokens:
    the app goes back to the login screen, where the user logs in with the new
    password. Errors: 400 {"code": "invalid_token"} (start again), or
    400 {"new_password": [...]} for a weak password (the token still works,
    so the user can try another).
    """

    def put(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            account_services.reset_password(data["uid"], data["reset_token"], data["new_password"])
        except DjangoValidationError as e:
            if hasattr(e, "error_dict"):  # {"new_password": [...]}
                raise ValidationError(e.message_dict)
            raise CodedError(e.messages[0], e.code)
        return Response({"detail": PASSWORD_CHANGED})


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
