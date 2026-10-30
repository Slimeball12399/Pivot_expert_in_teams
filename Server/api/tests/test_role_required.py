from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from api.decorators import role_required

PASSWORD = "Str0ng-test-pass!"


class AdminOnlyView(APIView):
    @role_required(User.Role.ADMIN)
    def get(self, request):
        return Response({"ok": True})


@api_view(["GET"])
@role_required(User.Role.SPEAKER)
def speaker_only(request):
    return Response({"ok": True})


class EitherRoleView(APIView):
    @role_required(User.Role.ADMIN, User.Role.SPEAKER)
    def get(self, request):
        return Response({"ok": True})


@api_view(["GET"])
@permission_classes([AllowAny])  # so only the decorator decides
@role_required(User.Role.ADMIN)
def admin_only_public(request):
    return Response({"ok": True})


def access_for(user):
    """An access token for `user`, like POST /api/auth/login/ gives."""
    return str(AccessToken.for_user(user))


def make_user(email, role):
    return User.objects.create_user(
        email, PASSWORD, first_name="Test", last_name="User", role=role)


class RoleRequiredTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin@example.com", User.Role.ADMIN)
        cls.speaker = make_user("speaker@example.com", User.Role.SPEAKER)

    def call(self, view, user=None, **headers):
        request = APIRequestFactory().get("/anything/", **headers)
        if user is not None:
            force_authenticate(request, user=user)
        return view(request)

    def test_status_by_user(self):
        admin_view = AdminOnlyView.as_view()
        either_view = EitherRoleView.as_view()
        # (label, view, user, expected status); user None = no token.
        cases = [
            ("class view, no token", admin_view, None, status.HTTP_401_UNAUTHORIZED),
            ("class view, wrong role", admin_view, "speaker", status.HTTP_403_FORBIDDEN),
            ("class view, right role", admin_view, "admin", status.HTTP_200_OK),
            ("function view, no token", speaker_only, None, status.HTTP_401_UNAUTHORIZED),
            ("function view, wrong role", speaker_only, "admin", status.HTTP_403_FORBIDDEN),
            ("function view, right role", speaker_only, "speaker", status.HTTP_200_OK),
            ("several roles, admin", either_view, "admin", status.HTTP_200_OK),
            ("several roles, speaker", either_view, "speaker", status.HTTP_200_OK),
            ("several roles, no token", either_view, None, status.HTTP_401_UNAUTHORIZED),
            # The decorator checks login itself, not only the default permission.
            ("public view, no token", admin_only_public, None, status.HTTP_401_UNAUTHORIZED),
            ("public view, wrong role", admin_only_public, "speaker", status.HTTP_403_FORBIDDEN),
            ("public view, right role", admin_only_public, "admin", status.HTTP_200_OK),
        ]
        for label, view, who, expected in cases:
            with self.subTest(label):
                user = getattr(self, who) if who else None
                self.assertEqual(self.call(view, user).status_code, expected)

    def test_with_real_tokens(self):
        """Through JWTAuthentication, not force_authenticate."""
        admin_view = AdminOnlyView.as_view()
        cases = [
            ("admin token", access_for(self.admin), status.HTTP_200_OK),
            ("speaker token", access_for(self.speaker), status.HTTP_403_FORBIDDEN),
            ("garbage token", "not-a-token", status.HTTP_401_UNAUTHORIZED),
        ]
        for label, token, expected in cases:
            with self.subTest(label):
                response = self.call(admin_view, HTTP_AUTHORIZATION=f"Bearer {token}")
                self.assertEqual(response.status_code, expected)

        # Last, because it changes the user.
        with self.subTest("role is read from the database, not the token"):
            token = access_for(self.speaker)
            self.speaker.role = User.Role.ADMIN
            self.speaker.save()
            response = self.call(admin_view, HTTP_AUTHORIZATION=f"Bearer {token}")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_needs_a_role(self):
        with self.assertRaises(ValueError):
            role_required()
