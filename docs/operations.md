# Container operations

## Run a published image

A GHCR release is not published yet. Until one is available, use the local build
in the [README](../README.md#local-quick-start-with-docker-compose).

For a published release, download `docker-compose.yml` and `.env.example` from
that release. No source checkout is needed. Copy `.env.example` to `.env`,
restrict its permissions to `600`, and configure a strong secret, public hosts,
HTTPS, and the trusted proxy as described in the README. Keep the secret and
volume name stable. Set `LINK_SHORTENER_IMAGE` to the chosen published version
or immutable digest, for example `ghcr.io/sjtrny/link-shortener:X.Y.Z` (replace
`X.Y.Z` with an actual release). Then run:

```bash
docker compose pull
docker compose up -d --wait
docker compose exec web python manage.py createsuperuser
```

Without Compose, replace `X.Y.Z` with the same published version:

```bash
docker run -d --name link-shortener -p 127.0.0.1:8000:8000 \
  --restart unless-stopped --stop-timeout 35 \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --env-file .env -v link-shortener-data:/app/data \
  ghcr.io/sjtrny/link-shortener:X.Y.Z
docker exec -it link-shortener python manage.py createsuperuser
```

Use one application container with a local Docker volume. Do not scale this
SQLite deployment or share the database over a network filesystem. Startup
applies migrations, performs optional admin bootstrap, and starts Gunicorn.
It does not download dependencies or collect static files. Custom commands
such as `python manage.py check` do not automatically run migrations or bootstrap.

The image's readiness check calls `/health/ready/` on loopback with a configured
allowed host. It needs no external network or trusted proxy. A healthy result
means Gunicorn can read the link table; it does not check DNS, TLS, or backups.
Docker records an unhealthy state but does not restart a container for that
state alone. Inspect failures with:

```bash
docker compose ps
docker compose logs --tail 100 web
```

## Data ownership

The application runs as UID/GID `10001:10001`. A new, empty named volume inherits
the image's data-directory ownership. Do not use the volume `nocopy` option.
The code, virtual environment, and static files remain root-owned and read-only.
Gunicorn uses the `/tmp` tmpfs for temporary files and has no control socket.

Existing data from a root-run image or a host bind mount may have a different
owner. Stop every container that uses the data, make a backup, and change the
owner once. For a named volume, replace the volume and image below with yours:

```bash
docker run --rm --user 0:0 --entrypoint chown \
  -v link-shortener-data:/app/data \
  link-shortener:local -R 10001:10001 /app/data
```

This helper runs as root only to repair ownership on the mounted data. Normal
startup never runs as root or changes ownership. Do not make the data directory
world-writable. With rootless Docker or user-namespace remapping, use the helper
instead of guessing host-side UIDs.

### Existing bind-mount installations

Earlier Compose files stored data at `./data`. The named-volume configuration
does not move those files. Stop the old app **before changing its Compose file**
and make a complete backup of `./data`, including SQLite sidecar files. Retain
the old image reference, Compose files, and `.env` securely.

You can keep the bind mount. Create `compose.data.yml`:

```yaml
services:
  web:
    volumes:
      - ./data:/app/data
```

Compose replaces the mount at `/app/data` when this override is included. Repair
the ownership from the installation directory, using your chosen image:

```bash
docker run --rm --user 0:0 --entrypoint chown \
  --mount "type=bind,src=$(pwd)/data,dst=/app/data" \
  link-shortener:local -R 10001:10001 /app/data
docker compose -f docker-compose.yml -f compose.data.yml up -d --wait
```

Use both Compose files for **all** subsequent commands, including backups and
upgrades, while that bind mount is in use. Bind paths are on the Docker daemon's
host, which may differ from your Docker client's machine.

Alternatively, archive the stopped old `data` directory with `tar -C data -czf
backup.tar.gz .` and follow the restore procedure below to import the archive
into a new named volume. Keep the original directory until the new installation
is confirmed to work. If the old data is not readable by your host user, run the
archive operation through a root helper with only that data directory mounted.

## Back up

Stop the application for a consistent SQLite snapshot. Do not copy a live
`db.sqlite3` file by itself. Back up the entire data directory so any SQLite
journal or WAL files stay with their database.

From the installation directory, choose a new archive name each time:

```bash
umask 077
mkdir -p backups
chmod 700 backups
docker compose stop web
docker compose run --rm --no-deps -T --entrypoint tar web \
  -C /app/data -czf - . > backups/data-YYYYMMDD-HHMMSS.tar.gz
docker compose start web
```

Check that the archive command succeeds before using its output as a backup.
Restart the app even if archiving fails. The helper bypasses application startup
and cannot apply migrations. Record the matching image version/digest and save
the matching Compose files and `.env` separately in secure storage. The database contains user
accounts and password hashes; protect the archive as well. Keep another copy
outside the Docker host and periodically restore a backup.

## Restore

Restore into a **new, empty named volume**, not on top of another database.
Retain the current volume so you can recover if the restore fails.

1. Stop the app with `docker compose stop web`.
2. Record the current image and volume names. In `.env`, set
   `LINK_SHORTENER_IMAGE` to the image used for the backup and
   `LINK_SHORTENER_DATA_VOLUME` to a new, unused name, such as
   `link-shortener-restored-YYYYMMDD-HHMMSS`. Retain the matching secret and
   production configuration. Clear all `DJANGO_SUPERUSER_*` values.
3. Import the archive. Compose creates the empty volume with the correct owner:

   ```bash
   docker compose run --rm --no-deps -T --entrypoint tar web \
     -C /app/data -xzf - --no-same-owner < backups/data-YYYYMMDD-HHMMSS.tar.gz
   ```

4. Check the restored database before starting the server:

   ```bash
   docker compose run --rm --no-deps -T web python -c 'import sqlite3; c = sqlite3.connect("file:/app/data/db.sqlite3?mode=ro", uri=True); result = c.execute("PRAGMA integrity_check").fetchall(); print(result); raise SystemExit(0 if result == [("ok",)] else 1)'
   ```

5. If the import and database check succeed, run `docker compose up -d --wait`.
   Confirm admin login and a known short-link redirect. Do not discard the old
   volume until these checks succeed and the restored data is correct.

Do not include `compose.data.yml` during a restore into a named volume. If a
restore attempt fails, use another new volume for the next attempt. Do not reuse
a partially restored directory.

## Upgrade and rollback

1. Record the current image reference and retain the current Compose files.
   Stop the app and make a backup as above, but omit `docker compose start web`.
   Leave the app stopped for the upgrade.
2. Read the new release notes. Change only `LINK_SHORTENER_IMAGE` to the chosen
   release, keeping the data-volume name, secret, and other settings.
3. Run `docker compose pull`, then `docker compose up -d --wait`. For a local
   source build, use the build command from the README instead of `pull`.
4. Check container health, logs, admin login, and a known redirect. Migrations
   run before the server starts. A migration failure prevents startup; inspect
   the logs before trying again.

Do not run old and new app containers against the same SQLite database at the
same time. For rollback, stop the new app, restore the pre-upgrade backup to a
new volume, and use its matching old image, Compose files, and configuration.
In particular, an older root-run image needs its original writable-root setup.
Changing the image alone does not reverse database migrations.

## Build metadata

Local builds use `unreleased` and `unknown` version/revision labels by default.
Supply release metadata when building a distributable image:

```bash
docker build --build-arg VERSION=X.Y.Z --build-arg REVISION="$(git rev-parse HEAD)" \
  -t link-shortener:X.Y.Z .
```

The image includes OCI title, description, source, version, and revision labels.
Dependencies come from `uv.lock`; `uv` is used only in the builder stage. Static
collection uses an ephemeral build-only key. Supply the real secret at runtime;
do not pass it as a Docker build argument.
