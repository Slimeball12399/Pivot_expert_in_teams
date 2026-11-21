"""A trainer's invitations to a speaker, as the speaker sees them."""

from rest_framework import serializers

from .common import DetailSerializer
from .users import InviteTrainerSerializer


class InviteSerializer(serializers.Serializer):
    """An open invitation in GET /api/invites/. replaces_trainer is the
    speaker's current trainer when accepting would replace them (the app
    warns "this will replace ..." before accepting), else null."""

    id = serializers.UUIDField()
    trainer = InviteTrainerSerializer(source="invited_by")
    replaces_trainer = InviteTrainerSerializer(allow_null=True)
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()


class InviteAcceptedSerializer(DetailSerializer):
    """Response of POST /api/invites/<id>/accept/: the new trainer, and the
    one they replaced (null when the speaker had none)."""

    trainer = InviteTrainerSerializer()
    previous_trainer = InviteTrainerSerializer(allow_null=True)
