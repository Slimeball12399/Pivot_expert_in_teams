"""The Sessions page, under sessions/ (web/urls/__init__.py)."""

from django.urls import path

from ..views import sessions

urlpatterns = [
    # GET: the Sessions page. POST: create a session (new session dialog).
    path("", sessions.session_list, name="sessions"),
    # One session: GET the page, PATCH (edit dialog), DELETE (confirm dialog).
    path("<uuid:session_id>/", sessions.session, name="session"),
]
