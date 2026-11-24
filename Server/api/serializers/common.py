"""Response shapes shared by every part of the API."""

from rest_framework import serializers


class DetailSerializer(serializers.Serializer):
    """A plain message, e.g. "If that account exists, we sent a code."."""

    detail = serializers.CharField()


class CodedErrorSerializer(DetailSerializer):
    """Errors the app reacts to by `code`: email_not_verified, invalid_code,
    invalid_token. `detail` is a message that can be shown as it is."""

    code = serializers.CharField()
