from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase, override_settings

from links.models import ShortLink


@override_settings(ALLOWED_HOSTS=['short.example'], SECURE_SSL_REDIRECT=True, STATIC_ROOT=None)
class ReadinessTests(TestCase):
    def test_empty_migrated_database_is_ready_over_http(self):
        response = self.client.get('/health/ready/', HTTP_HOST='short.example')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_database_failure_is_unavailable_without_exposing_details(self):
        with patch('config.health.ShortLink.objects.exists', side_effect=OperationalError('private database path')):
            response = self.client.get('/health/ready/', HTTP_HOST='short.example')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'unavailable'})
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_probe_supports_head(self):
        response = self.client.head('/health/ready/', HTTP_HOST='short.example')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'')

    def test_probe_rejects_write_methods(self):
        response = self.client.post('/health/ready/', HTTP_HOST='short.example')
        self.assertEqual(response.status_code, 405)

    def test_probe_does_not_bypass_host_validation(self):
        response = self.client.get('/health/ready/', HTTP_HOST='untrusted.example')
        self.assertEqual(response.status_code, 400)

    def test_only_exact_probe_path_is_exempt_from_https(self):
        for path in ('/', '/admin/', '/health/', '/health/ready', '/health/ready/extra/'):
            with self.subTest(path=path):
                response = self.client.get(path, HTTP_HOST='short.example')
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response['Location'], f'https://short.example{path}')

    def test_existing_health_short_code_is_not_shadowed(self):
        ShortLink.objects.create(short_code='health', target_url='https://destination.example/')
        response = self.client.get('/health/', HTTP_HOST='short.example', secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://destination.example/')
