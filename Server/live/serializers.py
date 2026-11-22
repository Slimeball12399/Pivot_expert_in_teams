"""The shape of the internal API's request bodies (live/views.py). Like the
API's serializers, they only check the shape; the rules (whose connection,
which state) are in the services."""

from rest_framework import serializers

from live.models import Connection

# Base serializer: the fields every connection request has, defined once here.


class ConnectionBaseSerializer(serializers.Serializer):
    """Which connection: the session, the user Django checked, and what it
    carries. Input of POST /offer/."""

    session_id = serializers.UUIDField()
    # The user id, as everywhere in Pivot (never a profile id).
    user_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=[kind.value for kind in Connection.Kind])

    def validate_kind(self, value):
        return Connection.Kind(value)


class AnswerSerializer(ConnectionBaseSerializer):
    """Input of POST /answer/: the base fields plus the browser's answer."""

    # Kept exactly as sent: an SDP ends with a line break.
    sdp = serializers.CharField(trim_whitespace=False)
