#!/bin/sh
# Shared by both run modes (design §3.2, D-031, D-033): setup, then exec the server
# command supplied by the active compose file.
set -eu
python manage.py migrate --noinput
python manage.py ensure_signing_key   # no-op if the file exists; refuses when DEBUG is off
exec "$@"                              # gunicorn (base) or runserver (override)
