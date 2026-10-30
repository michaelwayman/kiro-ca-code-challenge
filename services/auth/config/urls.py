from django.conf import settings
from django.urls import URLPattern, URLResolver, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config import health

urlpatterns: list[URLPattern | URLResolver] = [
    path("healthz/live", health.live, name="health-live"),
    path("healthz/ready", health.ready, name="health-ready"),
]

# The OpenAPI schema is always available via `manage.py spectacular`. The HTTP
# endpoints exist only when DEBUG is on (D-034.9, Req 9.6).
if settings.DEBUG:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    ]
