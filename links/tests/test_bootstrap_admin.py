from io import StringIO
import os
import secrets
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class BootstrapAdminTests(TestCase):
    def bootstrap(self, **overrides):
        env = {
            'DJANGO_SUPERUSER_USERNAME': '',
            'DJANGO_SUPERUSER_EMAIL': '',
            'DJANGO_SUPERUSER_PASSWORD': '',
            **overrides,
        }
        output = StringIO()
        with patch.dict(os.environ, env):
            call_command('bootstrap_admin', stdout=output)
        return output.getvalue()

    def credentials(self, **overrides):
        return {
            'DJANGO_SUPERUSER_USERNAME': 'bootstrap-owner',
            'DJANGO_SUPERUSER_EMAIL': 'owner@example.com',
            'DJANGO_SUPERUSER_PASSWORD': secrets.token_urlsafe(32),
            **overrides,
        }

    def test_no_credentials_does_not_create_a_default_admin(self):
        self.bootstrap()
        self.assertFalse(get_user_model().objects.exists())

    def test_partial_configuration_fails(self):
        for missing in ('DJANGO_SUPERUSER_USERNAME', 'DJANGO_SUPERUSER_EMAIL', 'DJANGO_SUPERUSER_PASSWORD'):
            with self.subTest(missing=missing), self.assertRaisesMessage(CommandError, 'Set all three'):
                self.bootstrap(**self.credentials(**{missing: ''}))
        self.assertFalse(get_user_model().objects.exists())

    def test_rejects_weak_example_and_user_similar_passwords(self):
        for password in ('short', '123456789012', 'password', 'change-me-now', 'bootstrap-owner'):
            with self.subTest(password_kind='invalid'), self.assertRaises(CommandError):
                self.bootstrap(**self.credentials(DJANGO_SUPERUSER_PASSWORD=password))
        self.assertFalse(get_user_model().objects.exists())

    def test_rejects_invalid_user_fields(self):
        for overrides in ({'DJANGO_SUPERUSER_USERNAME': 'not a username'}, {'DJANGO_SUPERUSER_EMAIL': 'not-an-email'}):
            with self.subTest(fields=list(overrides)), self.assertRaises(CommandError):
                self.bootstrap(**self.credentials(**overrides))
        self.assertFalse(get_user_model().objects.exists())

    def test_creates_a_valid_admin_without_logging_the_password(self):
        credentials = self.credentials()
        output = self.bootstrap(**credentials)
        user = get_user_model().objects.get(username=credentials['DJANGO_SUPERUSER_USERNAME'])
        self.assertTrue(user.is_active and user.is_staff and user.is_superuser)
        self.assertTrue(user.check_password(credentials['DJANGO_SUPERUSER_PASSWORD']))
        self.assertNotIn(credentials['DJANGO_SUPERUSER_PASSWORD'], output)

    def test_restart_does_not_reset_the_admin_password(self):
        credentials = self.credentials()
        self.bootstrap(**credentials)
        second = self.credentials(DJANGO_SUPERUSER_EMAIL='different@example.com')
        self.bootstrap(**second)
        user = get_user_model().objects.get(username=credentials['DJANGO_SUPERUSER_USERNAME'])
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertTrue(user.check_password(credentials['DJANGO_SUPERUSER_PASSWORD']))
        self.assertFalse(user.check_password(second['DJANGO_SUPERUSER_PASSWORD']))
        self.assertEqual(user.email, credentials['DJANGO_SUPERUSER_EMAIL'])

    def test_does_not_promote_an_existing_regular_user(self):
        credentials = self.credentials()
        user = get_user_model().objects.create_user(username=credentials['DJANGO_SUPERUSER_USERNAME'])
        with self.assertRaisesMessage(CommandError, 'not an active superuser'):
            self.bootstrap(**credentials)
        user.refresh_from_db()
        self.assertFalse(user.is_staff or user.is_superuser)
