#!/bin/sh
set -e

mkdir -p /app/data /app/staticfiles

uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput

uv run python manage.py bootstrap_admin

# Do not pass one-time bootstrap credentials to the long-running server.
unset DJANGO_SUPERUSER_USERNAME DJANGO_SUPERUSER_EMAIL DJANGO_SUPERUSER_PASSWORD

exec "$@"
