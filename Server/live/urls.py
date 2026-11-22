"""The live process's internal API (live/views.py), its whole URLconf
(pivot/settings_live.py). Not included in pivot/urls.py: the web process
never serves these."""

from django.urls import path

from . import views

urlpatterns = [
    path("offer/", views.offer, name="offer"),
    path("answer/", views.answer, name="answer"),
    path("sessions/<uuid:session_id>/close/", views.close_session, name="close_session"),
    path("talks/<uuid:talk_id>/stop-recording/", views.stop_recording, name="stop_recording"),
]
