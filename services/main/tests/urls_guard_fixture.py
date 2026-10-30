"""A throwaway URLconf for tests/test_url_protection.py's self-test, never used by the app."""

from django.urls import URLPattern, path
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class OpenByMistake(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class ProtectedByDefault(APIView):
    """No explicit classes: relies on the secure DRF defaults in settings."""

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


urlpatterns: list[URLPattern] = [
    path("open/", OpenByMistake.as_view(), name="open-by-mistake"),
    path("protected/", ProtectedByDefault.as_view(), name="protected-by-default"),
]
