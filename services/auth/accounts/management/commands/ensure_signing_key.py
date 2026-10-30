"""Make sure the RSA signing key exists before any server process starts (Req 5.3, 5.4, D-031).

Run by the entrypoint, once, before gunicorn/runserver, so workers never race to create it.

- Key file exists and is a valid RSA private key: no-op.
- Missing, DEBUG on: generate RSA-2048 and write it atomically with mode 0600.
- Missing, DEBUG off: refuse (exit non-zero) naming AUTH_SIGNING_KEY_PATH. Never generates.
- Present but unreadable or corrupt: refuse in both modes. An existing file is never
  overwritten, since it may be a mounted secret the operator needs to fix.

Only the path and the public ``kid`` are ever printed, never key material (Req 5.1, 11.4).
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.keys import (
    SigningKeyError,
    generate_private_key_file,
    load_private_key,
    public_jwk_and_kid,
)


class Command(BaseCommand):
    help = "Ensure the RSA signing key exists at AUTH_SIGNING_KEY_PATH (generated only in DEBUG)."

    def handle(self, *args: object, **options: object) -> None:
        path = Path(settings.AUTH_SIGNING_KEY_PATH)

        if path.exists():
            try:
                key = load_private_key(path)
            except SigningKeyError as exc:
                raise CommandError(
                    f"AUTH_SIGNING_KEY_PATH: {exc} Fix or remove the file; it is never "
                    "overwritten automatically."
                ) from None
            _, kid = public_jwk_and_kid(key)
            self.stdout.write(f"Signing key present at {path} (kid={kid}).")
            return

        if not settings.DEBUG:
            raise CommandError(
                f"AUTH_SIGNING_KEY_PATH: no signing key at {path}. With DJANGO_DEBUG off the "
                "key must be provisioned beforehand (e.g. `make prod-key` or a mounted "
                "secret); it is never generated."
            )

        try:
            key = generate_private_key_file(path)
        except OSError as exc:
            raise CommandError(
                f"AUTH_SIGNING_KEY_PATH: could not write a signing key to {path} ({exc.strerror})."
            ) from None
        _, kid = public_jwk_and_kid(key)
        self.stdout.write(self.style.SUCCESS(f"Generated signing key at {path} (kid={kid})."))
