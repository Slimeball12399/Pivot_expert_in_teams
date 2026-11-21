"""System endpoints, such as the health check."""

from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    """Response of GET /api/health/."""

    status = serializers.CharField()
    database = serializers.ChoiceField(choices=["ok", "down"])
