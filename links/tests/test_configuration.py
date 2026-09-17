import json
import os
from pathlib import Path
import runpy
import secrets
import subprocess
import sys
from unittest.mock import patch

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import SimpleTestCase, override_settings
from gunicorn.config import Config
from gunicorn.http.message import Request
from gunicorn.http.unreader import IterUnreader
from gunicorn.http.wsgi import create


ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PROBE = '''
import json
from config import settings
print(json.dumps({
    'debug': settings.DEBUG,
    'hosts': settings.ALLOWED_HOSTS,
    'origins': settings.CSRF_TRUSTED_ORIGINS,
    'redirect': settings.SECURE_SSL_REDIRECT,
    'session_secure': settings.SESSION_COOKIE_SECURE,
    'csrf_secure': settings.CSRF_COOKIE_SECURE,
    'hsts': settings.SECURE_HSTS_SECONDS,
    'hsts_subdomains': settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    'hsts_preload': settings.SECURE_HSTS_PRELOAD,
    'proxy_header': settings.SECURE_PROXY_SSL_HEADER,
    'forwarded_host': settings.USE_X_FORWARDED_HOST,
}))
'''


class ConfigurationTests(SimpleTestCase):
    def probe(self, **overrides):
        env = {name: value for name, value in os.environ.items() if not name.startswith('DJANGO_')}
        env.update(DJANGO_SECRET_KEY=secrets.token_urlsafe(64), DJANGO_ALLOWED_HOSTS='short.example')
        for name, value in overrides.items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value
        return subprocess.run(
            [sys.executable, '-c', SETTINGS_PROBE], cwd=ROOT, env=env,
            text=True, capture_output=True, check=False, timeout=10,
        )

    def test_defaults_protect_https_without_trusting_headers(self):
        result = self.probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(result.stdout)
        self.assertFalse(settings['debug'])
        for name in ('redirect', 'session_secure', 'csrf_secure'):
            self.assertTrue(settings[name], name)
        self.assertIsNone(settings['proxy_header'])
        self.assertFalse(settings['forwarded_host'])
        self.assertEqual(settings['hsts'], 0)
        self.assertFalse(settings['hsts_subdomains'])
        self.assertFalse(settings['hsts_preload'])

    def test_missing_weak_and_example_secrets_fail_without_echoing_them(self):
        for secret in (None, '', 'django-insecure-change-me', 'dev-secret-key-change-me',
                       'replace-this-with-a-real-secret', 'x' * 64, 'abcd' * 20,
                       'django-insecure-' + secrets.token_urlsafe(64)):
            with self.subTest(secret_kind='unset' if secret is None else 'invalid'):
                result = self.probe(DJANGO_SECRET_KEY=secret)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Set DJANGO_SECRET_KEY', result.stderr)
                if secret:
                    self.assertNotIn(secret, result.stdout + result.stderr)

    def test_hosts_must_be_explicit(self):
        for hosts in (None, '', ' , ', '*', 'short.example, *'):
            with self.subTest(hosts=hosts):
                result = self.probe(DJANGO_ALLOWED_HOSTS=hosts)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Set DJANGO_ALLOWED_HOSTS', result.stderr)

    def test_debug_does_not_bypass_configuration_requirements(self):
        result = self.probe(DJANGO_DEBUG='True', DJANGO_SECRET_KEY=None)
        self.assertNotEqual(result.returncode, 0)
        result = self.probe(DJANGO_DEBUG='True', DJANGO_ALLOWED_HOSTS='*')
        self.assertNotEqual(result.returncode, 0)

    def test_local_http_is_an_explicit_override_without_debug(self):
        result = self.probe(
            DJANGO_ALLOWED_HOSTS=' localhost, 127.0.0.1, ',
            DJANGO_CSRF_TRUSTED_ORIGINS=' http://localhost:8000, ',
            DJANGO_SECURE_SSL_REDIRECT='False',
            DJANGO_SESSION_COOKIE_SECURE='0',
            DJANGO_CSRF_COOKIE_SECURE='off',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(result.stdout)
        self.assertEqual(settings['hosts'], ['localhost', '127.0.0.1'])
        self.assertEqual(settings['origins'], ['http://localhost:8000'])
        for name in ('debug', 'redirect', 'session_secure', 'csrf_secure'):
            self.assertFalse(settings[name], name)

    def test_invalid_boolean_configuration_fails_closed(self):
        for name in ('DJANGO_DEBUG', 'DJANGO_SECURE_SSL_REDIRECT', 'DJANGO_SESSION_COOKIE_SECURE',
                     'DJANGO_CSRF_COOKIE_SECURE', 'DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS',
                     'DJANGO_SECURE_HSTS_PRELOAD'):
            with self.subTest(name=name):
                result = self.probe(**{name: 'typo'})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f'{name} must be True or False', result.stderr)

    def test_hsts_requires_a_non_negative_integer(self):
        for value in ('-1', 'invalid', ''):
            with self.subTest(value=value):
                result = self.probe(DJANGO_SECURE_HSTS_SECONDS=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('DJANGO_SECURE_HSTS_SECONDS must be a non-negative integer', result.stderr)

    def test_hsts_can_be_enabled_explicitly(self):
        result = self.probe(
            DJANGO_SECURE_HSTS_SECONDS='3600',
            DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS='yes',
            DJANGO_SECURE_HSTS_PRELOAD='True',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(result.stdout)
        self.assertEqual(settings['hsts'], 3600)
        self.assertTrue(settings['hsts_subdomains'])
        self.assertTrue(settings['hsts_preload'])


@override_settings(ALLOWED_HOSTS=['short.example'], SECURE_SSL_REDIRECT=True)
class ProxyTrustTests(SimpleTestCase):
    def response(self, peer='203.0.113.7', trusted=None, extra_headers='X-Forwarded-Proto: https\r\n'):
        env = {name: value for name, value in os.environ.items() if name != 'FORWARDED_ALLOW_IPS'}
        if trusted is not None:
            env['FORWARDED_ALLOW_IPS'] = trusted
        with patch.dict(os.environ, env, clear=True):
            config = Config()
            for name, value in runpy.run_path(str(ROOT / 'gunicorn.conf.py')).items():
                if name in config.settings:
                    config.set(name, value)
        raw = f'GET /example/ HTTP/1.1\r\nHost: short.example\r\n{extra_headers}\r\n'.encode()
        client = (peer, 45678)
        request = Request(config, IterUnreader([raw]), client)
        _, environ = create(request, None, client, ('127.0.0.1', 8000), config)
        return SecurityMiddleware(lambda request: HttpResponse('OK'))(WSGIRequest(environ))

    def test_direct_client_cannot_spoof_https(self):
        response = self.response()
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://short.example/example/')

    def test_loopback_is_not_implicitly_trusted(self):
        self.assertEqual(self.response(peer='127.0.0.1').status_code, 301)

    def test_allowed_proxy_sets_https_without_a_redirect_loop(self):
        self.assertEqual(self.response(peer='192.0.2.10', trusted='192.0.2.10').status_code, 200)

    def test_unlisted_peer_cannot_spoof_a_trusted_proxy(self):
        response = self.response(
            trusted='192.0.2.10',
            extra_headers='X-Forwarded-Proto: https\r\nX-Forwarded-For: 192.0.2.10\r\n',
        )
        self.assertEqual(response.status_code, 301)

    def test_proxy_http_requests_still_redirect(self):
        response = self.response(peer='192.0.2.10', trusted='192.0.2.10', extra_headers='X-Forwarded-Proto: http\r\n')
        self.assertEqual(response.status_code, 301)

    def test_alternative_scheme_and_host_headers_do_not_override_request(self):
        response = self.response(
            peer='192.0.2.10', trusted='192.0.2.10',
            extra_headers='X-Forwarded-SSL: on\r\nX-Forwarded-Host: attacker.example\r\n',
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://short.example/example/')
