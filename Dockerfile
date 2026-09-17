FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Apply distribution security updates between upstream Python image rebuilds.
# uv installs the application; pip and its bundled libraries are not needed.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall --yes pip

WORKDIR /app

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY config/ config/
COPY links/ links/
COPY manage.py ./
# This key exists only in the build process. No deployment credentials are needed.
RUN .venv/bin/python -c 'import os, secrets; os.environ.update(DJANGO_SECRET_KEY=secrets.token_urlsafe(64), DJANGO_ALLOWED_HOSTS="localhost", DJANGO_SETTINGS_MODULE="config.settings"); from django.core.management import execute_from_command_line; execute_from_command_line(["manage.py", "collectstatic", "--noinput"])'

FROM base AS runtime
ARG VERSION=unreleased
ARG REVISION=unknown
LABEL org.opencontainers.image.title="Link shortener" \
    org.opencontainers.image.description="Admin-managed Django link shortener with QR codes" \
    org.opencontainers.image.source="https://github.com/sjtrny/link-shortener" \
    org.opencontainers.image.version="${VERSION}" \
    org.opencontainers.image.revision="${REVISION}"

ENV PATH="/app/.venv/bin:$PATH"
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --home-dir /app app \
    && mkdir /app/data \
    && chown app:app /app/data \
    && chmod 700 /app/data

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/staticfiles /app/staticfiles
COPY config/ config/
COPY links/ links/
COPY manage.py gunicorn.conf.py ./
COPY --chmod=755 entrypoint.sh ./
# Normalize restrictive checkout modes without making application code writable.
RUN chmod -R u=rwX,go=rX /app/config /app/links \
    && chmod 644 /app/manage.py /app/gunicorn.conf.py

VOLUME ["/app/data"]
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-m", "config.healthcheck"]

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
