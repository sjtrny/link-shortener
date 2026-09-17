# Django link shortener

A minimal Django link shortener where links are created only in Django admin.

## Features

- Create short links in Django admin only
- Use a custom short code, or leave it blank to generate a random one
- Redirect from `/<code>/` to the destination URL
- Runs with gunicorn in Docker
- Serves Django admin static files with WhiteNoise

## Local quick start with Docker Compose

Copy the local configuration:

```bash
cp .env.example .env
chmod 600 .env
```

Generate a secret, then paste it into `DJANGO_SECRET_KEY` in `.env`:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Keep this secret stable across restarts. The app refuses to start without a
secret of at least 50 characters and 5 distinct characters, or with a
`django-insecure-` key. `DJANGO_ALLOWED_HOSTS` is also required; `*` is rejected.
These requirements apply with debug enabled too.

The example enables HTTP **only for local use**. Compose binds port 8000 to
`127.0.0.1`; it does not expose the app on every network interface. Do not use
the HTTP overrides for an internet-facing installation.

Start the app and create the first admin interactively:

```bash
docker compose up --build -d
docker compose exec web uv run python manage.py createsuperuser
```

There is no default admin account or password. Open:

- App: http://localhost:8000/
- Admin: http://localhost:8000/admin/

Compose stores the database in `./data`. `.env` and runtime data are ignored by
Git and excluded from the image build. Do not commit or share real credentials.

### Docker without Compose

Use the same configured `.env` file:

```bash
docker build -t django-link-shortener .
docker run -d --name link-shortener -p 127.0.0.1:8000:8000 \
  --env-file .env \
  -v link-shortener-data:/app/data \
  django-link-shortener
docker exec -it link-shortener uv run python manage.py createsuperuser
```

### Optional automated admin bootstrap

For an unattended first start, set all three `DJANGO_SUPERUSER_*` variables to
your chosen username, email, and a strong password. Leave all three empty to
disable bootstrap. Partial configuration, invalid user fields, weak passwords,
and the old example password cause startup to fail.

Bootstrap creates an admin only if the username is absent. It never resets an
existing admin's password or promotes an existing regular user. After the first
successful start, clear the three variables and recreate the container with
`docker compose up -d --force-recreate`. Keep the data directory. Clearing the
variables does not remove the account. The entrypoint also removes them from
the server process environment, but container configuration retains them until
the container is recreated without them.

## How to create a short link

1. Go to **Admin** → **Short links** → **Add short link**
2. Enter `target_url`
3. Either:
   - enter `short_code` yourself, or
   - leave `short_code` blank to auto-generate one
4. Save

Your short link will be available at:

```text
http://localhost:8000/<short_code>/
```

## Optional local run without Docker

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and prepare
`.env` as above. The project requires Python 3.13 or newer. Use the lockfile:

```bash
uv sync --locked --python 3.13
uv run --locked --env-file .env python manage.py migrate
uv run --locked --env-file .env python manage.py createsuperuser
uv run --locked --env-file .env python manage.py runserver
```

The app itself does not load `.env`; Compose, `docker run --env-file`, or
`uv run --env-file` supplies the environment.

## HTTPS and reverse proxies

For production, put Gunicorn behind an HTTPS reverse proxy and keep debug off.
In `.env`, replace the local hosts and origins, and enable the secure defaults:

```dotenv
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=short.example
DJANGO_CSRF_TRUSTED_ORIGINS=https://short.example
SHORTLINK_BASE_URL=https://short.example
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
```

Keep the generated secret; do not use an example value. The proxy must preserve
the public `Host` header, terminate TLS, redirect public HTTP traffic to HTTPS,
and **overwrite** `X-Forwarded-Proto` with the original request scheme. It must
not pass a client-supplied value through unchanged.

Set `FORWARDED_ALLOW_IPS` to the comma-separated source IP addresses that
Gunicorn actually sees for this proxy. No addresses are trusted by default,
including loopback. Do not use `*` on an accessible backend. Keep port 8000
reachable only by the controlled proxy, using loopback, a private container
network, or firewall rules. Configure admin login rate limiting at the proxy.

Gunicorn accepts `X-Forwarded-Proto: https` only from an allowed source and then
sets the WSGI scheme. Django deliberately does not trust the raw forwarded
header, which would bypass the source-IP check. `X-Forwarded-Host` and other
forwarded scheme headers are not used. For a different WSGI/ASGI server, set up
the equivalent trusted-proxy boundary in that server before deployment.

HSTS is opt-in because browsers retain it. After HTTPS works, start with
`DJANGO_SECURE_HSTS_SECONDS=3600` and increase it as appropriate. Only enable
`DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` if all subdomains support HTTPS, and
`DJANGO_SECURE_HSTS_PRELOAD` if you intend to meet the preload requirements.

Review deployment checks with the production environment:

```bash
docker compose exec web uv run python manage.py check --deploy
```

With HSTS disabled, Django reports `security.W004`. If HSTS is enabled but its
subdomain or preload options are off, it reports `security.W005` or
`security.W021`. Review these choices for your domain; do not enable them just
to suppress warnings. See [Django's deployment checklist](https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/)
and [Gunicorn's proxy settings](https://gunicorn.org/reference/settings/).

The current admin derives link URLs from the request origin. Canonical base-URL
and QR behavior are separate release follow-ups.

## Environment variables

| Variable | Default / purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Required strong, random Django secret. |
| `DJANGO_DEBUG` | `False`; enable only for local development. |
| `DJANGO_ALLOWED_HOSTS` | Required comma-separated hosts, without schemes or ports. No `*`. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Empty; optional comma-separated origins including schemes and any non-default ports. |
| `SHORTLINK_BASE_URL` | Empty; retained configuration, not yet used by the admin URL builder. |
| `DJANGO_SECURE_SSL_REDIRECT` | `True`; redirect HTTP requests to HTTPS. |
| `DJANGO_SESSION_COOKIE_SECURE` | `True`; send session cookies over HTTPS only. |
| `DJANGO_CSRF_COOKIE_SECURE` | `True`; send CSRF cookies over HTTPS only. |
| `DJANGO_SECURE_HSTS_SECONDS` | `0`; non-negative HSTS lifetime in seconds. |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | `False`; extend HSTS to subdomains. |
| `DJANGO_SECURE_HSTS_PRELOAD` | `False`; add the HSTS preload directive. |
| `FORWARDED_ALLOW_IPS` | Empty; proxy source IPs trusted by Gunicorn. |
| `DJANGO_SUPERUSER_USERNAME` | Empty; optional first-admin username. |
| `DJANGO_SUPERUSER_EMAIL` | Empty; optional first-admin email. |
| `DJANGO_SUPERUSER_PASSWORD` | Empty; optional first-admin password, checked by Django's password validators. |

Boolean values accept `True`/`False`, `1`/`0`, `yes`/`no`, or `on`/`off`,
case-insensitively. Other values fail startup. Debug mode does not disable the
HTTPS or secure-cookie settings; local HTTP overrides must be explicit.

## Notes

- The short code `admin` is reserved and cannot be used.
- SQLite is used by default and stored at `data/db.sqlite3`.
