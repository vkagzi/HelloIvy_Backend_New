import os
import subprocess

from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView
from django.db import connection
from django.conf import settings


def _get_git_commit():
    sha = os.environ.get("GIT_COMMIT_SHA")
    if sha:
        return sha
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


class HealthCheckView(APIView):
    """
    Health check endpoint for monitoring and load balancers.
    Returns system status and basic diagnostics.
    """

    renderer_classes = [JSONRenderer]
    allow_public = True  # Allow public access for health check

    def get(self, request: Request) -> Response:
        health_status = {
            "status": "healthy",
            "message": "It's working.",
            "version": _get_git_commit(),
        }

        # Check database connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status["database"] = "connected"
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["database"] = f"error: {str(e)}"
            return Response(health_status, status=503)

        # Add debug flag (useful for monitoring)
        health_status["debug"] = settings.DEBUG

        return Response(health_status, status=200)
