"""Shared token verification and permission checks (D-006).

The core package never imports Django. The DRF adapter lives in
``auth_common.drf`` and requires the ``drf`` extra.
"""

from importlib.metadata import version

__all__ = ["__version__"]

__version__: str = version("auth-common")
