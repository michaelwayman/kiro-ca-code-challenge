"""``{% load vite %}{% vite_asset "src/main.tsx" %}``. The logic lives in ``pages.vite``."""

from django import template
from django.utils.safestring import SafeString

from pages.vite import render_entry

register = template.Library()


@register.simple_tag
def vite_asset(entry: str) -> SafeString:
    return render_entry(entry)
