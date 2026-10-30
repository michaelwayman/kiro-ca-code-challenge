#!/bin/sh
# Shared by both run modes (design §3.2, D-033): setup, then exec the server command
# supplied by the active compose file. Static files are collected at image build time.
set -eu
python manage.py migrate --noinput
exec "$@"                              # gunicorn (base) or runserver (override)
