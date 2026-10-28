from django.db import connection
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import (
    HealthSerializer,
    RegisteredUserSerializer,
    SpeakerRegistrationSerializer,
)


@extend_schema(tags=["system"], responses=HealthSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])  # public on purpose: used to check the server is up
def health(request):
    """GET /api/health/ - is the server up and can it reach the database?"""
    try:
        connection.ensure_connection()
        db = "ok"
    except Exception:
        db = "down"
    return Response({"status": "ok", "database": db})


@extend_schema_view(post=extend_schema(
    tags=["auth"],
    request=SpeakerRegistrationSerializer,
    responses={201: RegisteredUserSerializer},
))
class RegisterView(CreateAPIView):
    """POST /api/auth/register/ - create a speaker account. Open to everyone."""

    serializer_class = SpeakerRegistrationSerializer
    permission_classes = [AllowAny]
