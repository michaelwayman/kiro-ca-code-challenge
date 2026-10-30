"""Liveness and readiness endpoints (Req 11.1).

These are plain Django views, not DRF views. They need no authentication,
content negotiation or schema, and staying outside DRF means a future change
to DRF's default authentication can never make them require a token.
"""

import logging

from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def live(request: HttpRequest) -> JsonResponse:
    """200 whenever the process can serve requests."""
    return JsonResponse({"status": "ok"})


@require_GET
def ready(request: HttpRequest) -> JsonResponse:
    """200 when this service's own database answers, otherwise 503."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.warning("readiness check failed: database unavailable", exc_info=True)
        return JsonResponse({"status": "unavailable", "database": "down"}, status=503)
    return JsonResponse({"status": "ok", "database": "up"})
