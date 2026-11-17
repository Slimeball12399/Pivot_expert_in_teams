"""System endpoints (tag "system")."""

from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from ..serializers import HealthSerializer


# auth=[]: no lock icon in Swagger UI (public endpoint).
@extend_schema(tags=["system"], responses=HealthSerializer, auth=[])
@api_view(["GET"])
@permission_classes([AllowAny])  # public on purpose: used to check the server is up
@authentication_classes([])  # never reads a token, so a bad one can't cause a 401
def health(request):
    """GET /api/health/ - is the server up and can it reach the database?"""
    try:
        connection.ensure_connection()
        db = "ok"
    except Exception:
        db = "down"
    return Response({"status": "ok", "database": db})
