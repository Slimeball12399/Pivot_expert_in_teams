from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login, name="login"),
    path("password-reset/", views.password_reset, name="password_reset"),
    path("verify-code/", views.verify_code, name="verify_code"),
]
