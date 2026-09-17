"""Run checks with generated, non-production configuration."""

import os
from pathlib import Path
import secrets
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith(('DJANGO_', 'LINK_SHORTENER_'))
        and key not in {'SHORTLINK_BASE_URL', 'FORWARDED_ALLOW_IPS'}
    }
    env.update(
        DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
        DJANGO_DEBUG='False',
        DJANGO_ALLOWED_HOSTS='short.example,testserver',
        DJANGO_CSRF_TRUSTED_ORIGINS='https://short.example',
        SHORTLINK_BASE_URL='https://short.example',
        # Use a fully HTTPS-enabled example domain for strict deployment checks.
        DJANGO_SECURE_HSTS_SECONDS='31536000',
        DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS='True',
        DJANGO_SECURE_HSTS_PRELOAD='True',
    )
    for arguments in (
        ['test', '--noinput'],
        ['makemigrations', '--check', '--dry-run'],
        ['check', '--deploy', '--fail-level', 'WARNING'],
    ):
        subprocess.run([sys.executable, 'manage.py', *arguments], cwd=ROOT, env=env, check=True)
    for files in (['docker-compose.yml'], ['docker-compose.yml', 'compose.build.yml']):
        command = ['docker', 'compose', '--env-file', '/dev/null']
        for filename in files:
            command.extend(['-f', filename])
        subprocess.run([*command, 'config', '--quiet'], cwd=ROOT, env=env, check=True)


if __name__ == '__main__':
    main()
