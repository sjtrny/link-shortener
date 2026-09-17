# Configuration

The README example sets the minimum localhost values directly in `compose.yaml`.
Edit its `environment` block when you need more settings.

The repository's `docker-compose.yml` also supports an `.env` file. Copy
`.env.example` to `.env` and keep it private. Compose reads it and passes the
values to the container. The application does not load `.env` itself.

## Settings

| Variable | Default / purpose |
| --- | --- |
| `LINK_SHORTENER_IMAGE` | `ghcr.io/sjtrny/link-shortener:latest`; image used by Compose. |
| `LINK_SHORTENER_DATA_VOLUME` | `link-shortener-data`; named volume used for SQLite data. |
| `DJANGO_SECRET_KEY` | Required random Django secret. |
| `DJANGO_DEBUG` | `False`; enable only for local development. |
| `DJANGO_ALLOWED_HOSTS` | Required comma-separated hostnames, without schemes or ports. `*` is rejected. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Empty; comma-separated origins with schemes and non-default ports. |
| `SHORTLINK_BASE_URL` | Empty; public HTTP(S) origin used for displayed and copied links and QR codes. |
| `DJANGO_SECURE_SSL_REDIRECT` | `True`; redirect HTTP requests to HTTPS. |
| `DJANGO_SESSION_COOKIE_SECURE` | `True`; send session cookies over HTTPS only. |
| `DJANGO_CSRF_COOKIE_SECURE` | `True`; send CSRF cookies over HTTPS only. |
| `DJANGO_SECURE_HSTS_SECONDS` | `0`; HSTS lifetime in seconds. |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `False`; extend HSTS to subdomains. |
| `DJANGO_SECURE_HSTS_PRELOAD` | `False`; add the HSTS preload directive. |
| `FORWARDED_ALLOW_IPS` | Empty; proxy source IP addresses trusted by Gunicorn. |
| `DJANGO_SUPERUSER_USERNAME` | Empty; optional first-admin username. |
| `DJANGO_SUPERUSER_EMAIL` | Empty; optional first-admin email. |
| `DJANGO_SUPERUSER_PASSWORD` | Empty; optional first-admin password. |

Boolean values accept `True`/`False`, `1`/`0`, `yes`/`no`, and `on`/`off`,
without case sensitivity. Other values stop startup.

The secret must have at least 50 characters and 5 distinct characters. Keys
that start with `django-insecure-` are rejected. Keep the same secret after a
restart or update.

## Public URLs and QR codes

Set `SHORTLINK_BASE_URL` to the public origin, such as
`https://go.example.com`. It can include a non-default port, but not credentials,
a path, a query, or a fragment.

When the setting is empty, links use the validated host and scheme of the
request. Set it explicitly if admin and redirects use different hostnames. Both
hostnames must still be present in `DJANGO_ALLOWED_HOSTS` and routed to the app.

The short code `admin` is reserved. QR images require staff permission to view
short links. Browser clipboard access normally requires HTTPS or localhost.

## HTTPS proxy

For a public installation, put Gunicorn behind a controlled HTTPS reverse proxy:

```dotenv
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=short.example
DJANGO_CSRF_TRUSTED_ORIGINS=https://short.example
SHORTLINK_BASE_URL=https://short.example
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
```

The proxy must preserve the public `Host` header, redirect public HTTP traffic
to HTTPS, and replace `X-Forwarded-Proto` with the original request scheme. Do
not pass a client-supplied value through unchanged.

Set `FORWARDED_ALLOW_IPS` to the comma-separated source IP addresses that
Gunicorn sees for the proxy. No address is trusted by default. Do not use `*` on
an accessible backend. Keep port 8000 reachable only by the proxy and configure
admin login rate limiting there.

HSTS is optional because browsers retain it. After HTTPS works, start with
`DJANGO_SECURE_HSTS_SECONDS=3600`. Enable the subdomain and preload options only
when every affected hostname meets those requirements.

Check the production environment with:

```sh
docker compose exec web python manage.py check --deploy
```

## Admin bootstrap

The interactive `createsuperuser` command in the README is the default. For an
unattended first start, set all three `DJANGO_SUPERUSER_*` values. Partial or
invalid settings stop startup.

Bootstrap creates the account only when its username is absent. It never resets
an existing password or promotes a regular user. Clear all three values and
recreate the container after the first successful start:

```sh
docker compose up -d --force-recreate
```

## Local Python

The project requires Python 3.13 or newer and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked --python 3.13
uv run --locked --env-file .env python manage.py migrate
uv run --locked --env-file .env python manage.py createsuperuser
uv run --locked --env-file .env python manage.py runserver
```
