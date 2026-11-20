from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views.auth import (
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    RefreshView,
    RegisterView,
    VerifyEmailView,
)
from .views.invites import InviteAcceptView, InviteDeclineView, InviteListView
from .views.sessions import SessionDetailView, SessionJoinView, SessionListView
from .views.talks import TalkDetailView, TalkEndView
from .views.system import health

app_name = "api"

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    # POST: send a new code. PUT: verify with the code.
    path("auth/verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("auth/password-reset/verify/", PasswordResetVerifyView.as_view(),
         name="password-reset-verify"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(),
         name="password-reset-confirm"),
    path("me/", MeView.as_view(), name="me"),
    path("invites/", InviteListView.as_view(), name="invites"),
    path("invites/<uuid:invite_id>/accept/", InviteAcceptView.as_view(), name="invite-accept"),
    path("invites/<uuid:invite_id>/decline/", InviteDeclineView.as_view(), name="invite-decline"),
    # GET: list. POST: create.
    path("sessions/", SessionListView.as_view(), name="sessions"),
    # GET: the session with its talks. PATCH: change. DELETE: cancel.
    path("sessions/<uuid:session_id>/", SessionDetailView.as_view(), name="session"),
    path("sessions/<uuid:session_id>/join/", SessionJoinView.as_view(), name="session-join"),
    path("talks/<uuid:talk_id>/", TalkDetailView.as_view(), name="talk"),
    path("talks/<uuid:talk_id>/end/", TalkEndView.as_view(), name="talk-end"),

    # API docs: raw OpenAPI schema and Swagger UI
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
]
