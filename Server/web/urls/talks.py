"""Talks, under talks/ (web/urls/__init__.py)."""

from django.urls import path

from ..views import talks

urlpatterns = [
    # GET: one talk's graphs as JSON (the session page's talks card).
    path("<uuid:talk_id>/", talks.talk, name="talk"),
]
