from django.shortcuts import render

# Create your views here.
from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(["GET"])
def health(request):
    try:
        connection.ensure_connection()
        db = "ok"
    except Exception:
        db = "down"
    return Response({"status": "ok", "database": db})