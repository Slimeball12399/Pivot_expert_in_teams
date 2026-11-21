"""Sessions, under sessions/ (api/urls/__init__.py)."""

from django.urls import path

from ..views.sessions import SessionDetailView, SessionJoinView, SessionListView

urlpatterns = [
    # GET: list. POST: create.
    path("", SessionListView.as_view(), name="sessions"),
    # GET: the session with its talks. PATCH: change. DELETE: cancel.
    path("<uuid:session_id>/", SessionDetailView.as_view(), name="session"),
    path("<uuid:session_id>/join/", SessionJoinView.as_view(), name="session-join"),
]
