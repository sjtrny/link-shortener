"""Probe Gunicorn locally without proxy environment variables or HTTPS trust."""

import http.client
import json
import os
import sys


def main():
    hosts = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',') if host.strip()]
    if not hosts:
        return 1
    # Django's leading-dot form also permits the domain itself.
    host = hosts[0].lstrip('.')
    connection = http.client.HTTPConnection('127.0.0.1', 8000, timeout=3)
    try:
        connection.request('GET', '/health/ready/', headers={'Host': host})
        response = connection.getresponse()
        if response.status == 200 and json.loads(response.read(1024)) == {'status': 'ok'}:
            return 0
    except (OSError, ValueError, http.client.HTTPException):
        pass
    finally:
        connection.close()
    print('Readiness check failed.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
