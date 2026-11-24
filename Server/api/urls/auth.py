"""Registering, logging in and out, email verification and the password
reset, under auth/ (api/urls/__init__.py)."""

from django.urls import path

from ..views.auth import (
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    RefreshView,
    RegisterView,
    VerifyEmailView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshView.as_view(), name="refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    # POST: send a new code. PUT: verify with the code.
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password-reset/verify/", PasswordResetVerifyView.as_view(),
         name="password-reset-verify"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(),
         name="password-reset-confirm"),
]
