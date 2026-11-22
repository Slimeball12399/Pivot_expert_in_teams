"""The Sessions page, one session and its live screen, under sessions/ (web/urls/__init__.py)."""

from django.urls import path

from ..views import sessions

urlpatterns = [
    # GET: the Sessions page. POST: create a session (new session dialog).
    path("", sessions.session_list, name="sessions"),
    # One session: GET the page, PATCH (edit dialog), DELETE (confirm dialog).
    path("<uuid:session_id>/", sessions.session, name="session"),
    # GET: its live screen (only while live). POST: start it, then the live screen.
    path("<uuid:session_id>/live/", sessions.session_live, name="session_live"),
    # The live screen's WebRTC connection: GET the offer, POST the answer (JSON).
    path("<uuid:session_id>/connect/", sessions.session_connect, name="session_connect"),
    # POST: Finish session (the confirm dialog).
    path("<uuid:session_id>/finish/", sessions.session_finish, name="session_finish"),
]
