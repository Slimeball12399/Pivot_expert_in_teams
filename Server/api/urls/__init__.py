"""The API's URLs, one module per area. Every name is in the "api" namespace
(reverse("api:sessions")): the included modules have no app_name of their own."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from ..views.auth import MeView
from ..views.system import health

app_name = "api"

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/", include("api.urls.auth")),
    path("me/", MeView.as_view(), name="me"),
    path("invites/", include("api.urls.invites")),
    path("sessions/", include("api.urls.sessions")),
    path("talks/", include("api.urls.talks")),

    # API docs: raw OpenAPI schema and Swagger UI
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
]
