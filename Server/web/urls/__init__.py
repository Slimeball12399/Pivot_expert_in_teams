"""The web app's URLs, one module per area. Every name is in the "web"
namespace ({% url 'web:sessions' %}): the included modules have no app_name
of their own."""

from django.urls import include, path

from ..views import pages

app_name = "web"

urlpatterns = [
    path("", pages.home, name="home"),
    # login/, logout/, the password reset and users/.
    path("", include("web.urls.accounts")),
    path("sessions/", include("web.urls.sessions")),
    path("talks/", include("web.urls.talks")),
]
