# link-shortener

Admin-managed Django link shortener with QR codes.

## Run

Create `compose.yaml`:

```yaml
services:
  app:
    image: ghcr.io/sjtrny/link-shortener:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DJANGO_SECRET_KEY:
      DJANGO_ALLOWED_HOSTS: localhost
      DJANGO_SECURE_SSL_REDIRECT: "False"
      DJANGO_SESSION_COOKIE_SECURE: "False"
      DJANGO_CSRF_COOKIE_SECURE: "False"
    volumes:
      - data:/app/data

volumes:
  data:
    name: link-shortener-data
```

Django uses `DJANGO_SECRET_KEY` for cryptographic signing. Generate a random
value once, keep it private, and put it after `DJANGO_SECRET_KEY:`:

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
```

Start the app and create an admin account:

```sh
docker compose up -d --wait
docker compose exec app python manage.py createsuperuser
```

Open <http://localhost:8000/admin/>.

The example listens on localhost and uses HTTP. Configure an HTTPS proxy before
you expose the app to a network.

## Links

In Django admin, add a **Short link** with a destination URL. Enter a custom
code or leave it empty to generate one.

The saved record shows the short URL and its QR code. You can copy the URL, open
the QR image, or download it as a PNG. The QR code points to the short URL, so
you can change the destination later.

## Documentation

- [Configuration](docs/configuration.md)
- [Operations](docs/operations.md)
- [CI and local checks](docs/ci.md)
- [Container publishing](docs/releasing.md)

## State and restart

SQLite data is stored in the `link-shortener-data` Docker volume. Replacing the
container keeps this data. Do not use `docker compose down --volumes` unless you
want to delete it.

Run one application container. Startup applies database migrations before it
starts Gunicorn.
