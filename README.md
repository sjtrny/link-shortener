# Django link shortener

A minimal Django link shortener where links are created only in Django admin.

## Features

- Create short links in Django admin only
- Use a custom short code, or leave it blank to generate a random one
- Redirect from `/<code>/` to the destination URL
- Runs with gunicorn in Docker
- Serves Django admin static files with WhiteNoise

## Quick start with Docker

Build the image:

```bash
docker build -t django-link-shortener .
```

Run it:

```bash
docker run --rm -p 8000:8000 \
  -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
  -e SHORTLINK_BASE_URL=http://localhost:8000 \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@example.com \
  -e DJANGO_SUPERUSER_PASSWORD=change-me-now \
  django-link-shortener
```

Then open:

- App: http://localhost:8000/
- Admin: http://localhost:8000/admin/

Log into the admin with the superuser credentials you passed in.

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

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Environment variables

- `DJANGO_SECRET_KEY` — Django secret key
- `DJANGO_DEBUG` — `True` or `False` (default: `False`)
- `DJANGO_ALLOWED_HOSTS` — comma-separated hosts (default: `*`)
- `DJANGO_CSRF_TRUSTED_ORIGINS` — comma-separated origins
- `SHORTLINK_BASE_URL` — optional base URL shown in admin, e.g. `http://localhost:8000`
- `DJANGO_SUPERUSER_USERNAME` — optional auto-created admin username on container start
- `DJANGO_SUPERUSER_EMAIL` — optional auto-created admin email
- `DJANGO_SUPERUSER_PASSWORD` — optional auto-created admin password

## Notes

- The short code `admin` is reserved and cannot be used.
- SQLite is used by default and stored at `data/db.sqlite3`.
