#!/bin/sh
set -e
umask 077

# Management commands and backup tools must not change the schema on startup.
if [ "${1:-}" = "gunicorn" ]; then
    if [ ! -w /app/data ] || { [ -e /app/data/db.sqlite3 ] && [ ! -w /app/data/db.sqlite3 ]; }; then
        echo "The data directory and database must be writable by UID/GID 10001:10001. See the data ownership instructions in docs/operations.md." >&2
        exit 1
    fi

    python manage.py migrate --noinput
    python manage.py bootstrap_admin

    # Do not pass one-time bootstrap credentials to the long-running server.
    unset DJANGO_SUPERUSER_USERNAME DJANGO_SUPERUSER_EMAIL DJANGO_SUPERUSER_PASSWORD
fi

exec "$@"
