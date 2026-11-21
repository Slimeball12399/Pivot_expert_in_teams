"""A speaker's invites, under invites/ (api/urls/__init__.py)."""

from django.urls import path

from ..views.invites import InviteAcceptView, InviteDeclineView, InviteListView

urlpatterns = [
    path("", InviteListView.as_view(), name="invites"),
    path("<uuid:invite_id>/accept/", InviteAcceptView.as_view(), name="invite-accept"),
    path("<uuid:invite_id>/decline/", InviteDeclineView.as_view(), name="invite-decline"),
]
