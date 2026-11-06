from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    RefreshView,
    RegisterView,
    VerifyEmailView,
    health,
)

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

    # API docs: raw OpenAPI schema and Swagger UI
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
]
