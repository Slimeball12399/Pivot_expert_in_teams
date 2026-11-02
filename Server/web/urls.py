from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login, name="login"),
    # Password reset: email -> code -> new password.
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("verify-code/", views.verify_code, name="verify_code"),
    path("verify-code/resend/", views.resend_code, name="resend_code"),
    path("password-reset/", views.password_reset, name="password_reset"),
]
