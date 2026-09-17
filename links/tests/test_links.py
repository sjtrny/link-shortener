from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from links.models import ALPHABET, ShortLink


class ShortCodeTests(TestCase):
    def test_generated_code_is_saved_and_resolves_to_its_path(self):
        link = ShortLink.objects.create(target_url='https://destination.example/')
        link.refresh_from_db()
        self.assertEqual(len(link.short_code), 6)
        self.assertTrue(set(link.short_code) <= set(ALPHABET))
        self.assertEqual(link.get_absolute_url(), f'/{link.short_code}/')

    def test_custom_code_is_normalized_before_saving(self):
        link = ShortLink.objects.create(short_code='My-Link_2', target_url='https://destination.example/')
        link.refresh_from_db()
        self.assertEqual(link.short_code, 'my-link_2')

    def test_generated_collision_does_not_replace_an_existing_link(self):
        original = ShortLink.objects.create(short_code='taken1', target_url='https://original.example/')
        with patch('links.models.get_random_string', side_effect=['taken1', 'fresh1']):
            created = ShortLink.objects.create(target_url='https://new.example/')
        original.refresh_from_db()
        self.assertEqual(original.target_url, 'https://original.example/')
        self.assertEqual(created.short_code, 'fresh1')
        self.assertEqual(ShortLink.objects.count(), 2)

    def test_database_enforces_uniqueness_without_model_validation(self):
        original = ShortLink.objects.create(short_code='taken1', target_url='https://original.example/')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ShortLink.objects.bulk_create([
                ShortLink(short_code='taken1', target_url='https://replacement.example/'),
            ])
        original.refresh_from_db()
        self.assertEqual(original.target_url, 'https://original.example/')
        self.assertEqual(ShortLink.objects.count(), 1)

    def test_reserved_invalid_and_overlong_custom_codes_are_rejected(self):
        for code in ('admin', 'ADMIN', 'not a slug', 'a' * 33):
            with self.subTest(code=code), self.assertRaises(ValidationError):
                ShortLink(short_code=code, target_url='https://destination.example/').full_clean()


@override_settings(
    ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False, STATIC_ROOT=None,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class LinkAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.link = ShortLink.objects.create(short_code='example', target_url='https://destination.example/?a=1&b=2')
        ShortLink.objects.create(short_code='inactive', target_url='https://hidden.example/', is_active=False)

    def test_active_links_redirect_anonymous_visitors_case_insensitively(self):
        for path in ('/example/', '/EXAMPLE/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response['Location'], self.link.target_url)

    def test_inactive_and_missing_links_return_404(self):
        for path in ('/inactive/', '/missing/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_head_follows_the_same_redirect_without_a_body(self):
        response = self.client.head('/example/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], self.link.target_url)
        self.assertEqual(response.content, b'')

    def test_anonymous_users_cannot_create_links_in_admin(self):
        response = self.client.post(reverse('admin:links_shortlink_add'), {
            'short_code': 'forbidden', 'target_url': 'https://destination.example/', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response['Location'])
        self.assertFalse(ShortLink.objects.filter(short_code='forbidden').exists())

    def test_staff_without_add_permission_cannot_create_links(self):
        user = get_user_model().objects.create_user(username='staff', is_staff=True)
        self.client.force_login(user)
        response = self.client.post(reverse('admin:links_shortlink_add'), {
            'short_code': 'forbidden', 'target_url': 'https://destination.example/', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ShortLink.objects.filter(short_code='forbidden').exists())
