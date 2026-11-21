"""Talks, under talks/ (api/urls/__init__.py)."""

from django.urls import path

from ..views.talks import TalkDetailView, TalkEndView

urlpatterns = [
    path("<uuid:talk_id>/", TalkDetailView.as_view(), name="talk"),
    path("<uuid:talk_id>/end/", TalkEndView.as_view(), name="talk-end"),
]
