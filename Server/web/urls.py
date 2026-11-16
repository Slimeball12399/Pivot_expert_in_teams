from django.urls import path

from .views import auth, pages, users

app_name = "web"

urlpatterns = [
    path("", pages.home, name="home"),
    path("users/", users.user_list, name="users"),
    path("users/invite/", users.invite_create, name="invite_create"),
    path("users/invite/suggestions/", users.invite_suggestions, name="invite_suggestions"),
    path("users/invites/<uuid:invite_id>/resend/", users.invite_resend, name="invite_resend"),
    path("users/invites/<uuid:invite_id>/cancel/", users.invite_cancel, name="invite_cancel"),
    path("login/", auth.login, name="login"),
    # Password reset: email -> code -> new password.
    path("forgot-password/", auth.forgot_password, name="forgot_password"),
    path("verify-code/", auth.verify_code, name="verify_code"),
    path("verify-code/resend/", auth.resend_code, name="resend_code"),
    path("password-reset/", auth.password_reset, name="password_reset"),
]
