"""Executed inside test containers over stdin; never copied into the image."""

from http.cookies import SimpleCookie
import http.client
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import urlencode

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.urls import reverse
from PIL import Image

from links.models import ShortLink


def seed():
    assert not ShortLink.objects.exists(), 'Expected a fresh database'
    ShortLink.objects.create(short_code='persist', target_url='https://destination.example/?a=1&b=2')
    ShortLink.objects.create(short_code='inactive', target_url='https://hidden.example/', is_active=False)
    ShortLink.objects.create(short_code='health', target_url='https://destination.example/health')


def persisted():
    assert ShortLink.objects.count() == 3
    assert ShortLink.objects.get(short_code='persist').target_url == 'https://destination.example/?a=1&b=2'
    assert not ShortLink.objects.get(short_code='inactive').is_active
    user = get_user_model().objects.get(username='ci-admin')
    assert user.is_active and user.is_staff and user.is_superuser
    assert user.check_password(os.environ['DJANGO_SUPERUSER_PASSWORD'])


def runtime():
    assert os.getuid() == os.getgid() == 10001
    assert shutil.which('uv') is None
    assert shutil.which('pip') is None
    assert not os.access('/app/manage.py', os.W_OK)
    assert not os.access('/app/.venv', os.W_OK)
    assert not os.access('/app/staticfiles', os.W_OK)
    assert Path('/app/data/db.sqlite3').stat().st_uid == 10001
    assert Path('/app/staticfiles/staticfiles.json').is_file()
    for path in ('.env', '.git', 'TODO.md', 'uv.lock', 'ci'):
        assert not (Path('/app') / path).exists(), path
    assert b'DJANGO_SUPERUSER_' not in Path('/proc/1/environ').read_bytes()


def http_checks():
    connection = http.client.HTTPConnection('127.0.0.1', 8000, timeout=5)
    cookies = SimpleCookie()

    def request(path, *, https=True, host='short.example', method='GET', data=None, authenticated=False):
        headers = {'Host': host}
        if https:
            headers['X-Forwarded-Proto'] = 'https'
        if authenticated:
            headers['Cookie'] = '; '.join(f'{key}={value.value}' for key, value in cookies.items())
        if data is not None:
            headers.update({'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://short.example'})
        connection.request(method, path, body=urlencode(data) if data is not None else None, headers=headers)
        response = connection.getresponse()
        body = response.read()
        for key, value in response.getheaders():
            if key.lower() == 'set-cookie':
                cookies.load(value)
        return response, body

    try:
        response, _ = request('/', https=False)
        assert response.status == 301 and response.getheader('Location') == 'https://short.example/'
        response, body = request('/health/ready/', https=False)
        assert response.status == 200 and json.loads(body) == {'status': 'ok'}
        response, _ = request('/health/ready/', host='untrusted.example', https=False)
        assert response.status == 400
        for code in ('persist', 'PERSIST'):
            response, _ = request(f'/{code}/')
            assert response.status == 302
            assert response.getheader('Location') == 'https://destination.example/?a=1&b=2'
        for code in ('inactive', 'missing'):
            assert request(f'/{code}/')[0].status == 404
        assert request('/health/')[0].getheader('Location') == 'https://destination.example/health'
        response, _ = request('/admin/')
        assert response.status == 302 and '/admin/login/' in response.getheader('Location')
        link = ShortLink.objects.get(short_code='persist')
        qr_path = reverse('admin:links_shortlink_qr_code', args=[link.pk])
        assert request(qr_path)[0].status == 302
        assert request('/admin/login/')[0].status == 200
        response, _ = request('/admin/login/?next=/admin/', method='POST', authenticated=True, data={
            'username': 'ci-admin', 'password': os.environ['DJANGO_SUPERUSER_PASSWORD'],
            'csrfmiddlewaretoken': cookies['csrftoken'].value, 'next': '/admin/',
        })
        assert response.status == 302 and response.getheader('Location') == '/admin/'
        assert cookies['sessionid']['secure'] and cookies['sessionid']['httponly']
        response, body = request('/admin/links/shortlink/', authenticated=True)
        assert response.status == 200 and b'https://go.example/persist/' in body
        response, body = request(qr_path, authenticated=True)
        assert response.status == 200 and response.getheader('Content-Type') == 'image/png'
        with Image.open(BytesIO(body)) as image:
            image.verify()
        manifest = json.loads(Path('/app/staticfiles/staticfiles.json').read_text())
        for source in ('admin/css/base.css', 'links/admin.js'):
            response, body = request('/static/' + manifest['paths'][source])
            assert response.status == 200 and body
            assert 'immutable' in response.getheader('Cache-Control')
    finally:
        connection.close()


for check in sys.argv[1:]:
    {'seed': seed, 'persisted': persisted, 'runtime': runtime, 'http': http_checks}[check]()
    print(f'Passed container check: {check}', flush=True)
