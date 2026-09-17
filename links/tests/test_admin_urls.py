from io import BytesIO
from unittest.mock import patch

from PIL import Image
import qrcode
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from links.admin import ShortLinkAdmin
from links.models import ShortLink


@override_settings(
    ALLOWED_HOSTS=['testserver', 'admin.example', 'second.example'],
    SHORTLINK_BASE_URL='https://go.example',
    SECURE_SSL_REDIRECT=False,
    STATIC_ROOT=None,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class AdminURLTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username='owner', is_staff=True, is_superuser=True)
        cls.viewer = User.objects.create_user(username='viewer', is_staff=True)
        cls.editor = User.objects.create_user(username='editor', is_staff=True)
        cls.staff = User.objects.create_user(username='staff', is_staff=True)
        cls.add_only = User.objects.create_user(username='add-only', is_staff=True)
        cls.nonstaff = User.objects.create_user(username='nonstaff')
        cls.inactive = User.objects.create_user(username='inactive', is_staff=True, is_active=False)
        for user, codename in ((cls.viewer, 'view_shortlink'), (cls.editor, 'change_shortlink'),
                               (cls.add_only, 'add_shortlink')):
            user.user_permissions.add(Permission.objects.get(content_type__app_label='links', codename=codename))
        cls.link = ShortLink.objects.create(short_code='example', target_url='https://destination.example/page')

    def setUp(self):
        self.client.force_login(self.owner)
        self.change_url = reverse('admin:links_shortlink_change', args=[self.link.pk])
        self.qr_url = reverse('admin:links_shortlink_qr_code', args=[self.link.pk])
        self.list_url = reverse('admin:links_shortlink_changelist')

    def qr_response(self, path=None, **kwargs):
        payloads = []
        add_data = qrcode.QRCode.add_data

        def record(qr, data, *args, **options):
            payloads.append(data)
            return add_data(qr, data, *args, **options)

        with patch.object(qrcode.QRCode, 'add_data', record):
            response = self.client.get(path or self.qr_url, **kwargs)
        return response, payloads

    def assert_png(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        with Image.open(BytesIO(response.content)) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.width, image.height)
            self.assertGreater(image.width, 0)
            image.verify()

    def test_canonical_origin_controls_both_admin_pages_and_qr_payload(self):
        expected = 'https://go.example/example/'
        for path in (self.list_url, self.change_url):
            response = self.client.get(path, HTTP_HOST='admin.example')
            self.assertContains(response, f'value="{expected}"')
            self.assertNotContains(response, 'http://admin.example/example/')
        response = self.client.get(self.change_url, HTTP_HOST='admin.example')
        self.assertContains(response, f'href="{expected}"')
        self.assertContains(response, f'alt="QR code for {expected}"')
        response, payloads = self.qr_response(HTTP_HOST='admin.example')
        self.assert_png(response)
        self.assertEqual(payloads, [expected])
        self.assertNotIn(self.link.target_url, payloads)
        self.assertEqual(response['Content-Disposition'], 'inline; filename="shortlink-example.png"')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('private', response['Cache-Control'])

    @override_settings(SHORTLINK_BASE_URL='http://localhost:8080')
    def test_configured_http_origin_and_port_are_preserved(self):
        response, payloads = self.qr_response(secure=True, HTTP_HOST='admin.example')
        self.assert_png(response)
        self.assertEqual(payloads, ['http://localhost:8080/example/'])

    @override_settings(SHORTLINK_BASE_URL='')
    def test_fresh_admin_qr_uses_the_current_https_request(self):
        fresh_admin = ShortLinkAdmin(ShortLink, admin.AdminSite())
        request = RequestFactory().get(self.qr_url, secure=True, HTTP_HOST='second.example:8443')
        request.user = self.owner
        payloads = []
        add_data = qrcode.QRCode.add_data

        def record(qr, data, *args, **kwargs):
            payloads.append(data)
            return add_data(qr, data, *args, **kwargs)

        with patch.object(qrcode.QRCode, 'add_data', record):
            response = fresh_admin.admin_site.admin_view(fresh_admin.qr_code_image_view)(request, str(self.link.pk))
        self.assert_png(response)
        self.assertEqual(payloads, ['https://second.example:8443/example/'])

    @override_settings(SHORTLINK_BASE_URL='')
    def test_later_qr_request_does_not_reuse_an_earlier_admin_host(self):
        first = self.client.get(self.change_url, HTTP_HOST='admin.example')
        self.assertContains(first, 'value="http://admin.example/example/"')
        response, payloads = self.qr_response(secure=True, HTTP_HOST='second.example')
        self.assert_png(response)
        self.assertEqual(payloads, ['https://second.example/example/'])

    @override_settings(SHORTLINK_BASE_URL='')
    def test_interleaved_admin_renderers_keep_their_own_request_origin(self):
        model_admin = admin.site._registry[ShortLink]
        request_a = RequestFactory().get(self.change_url, HTTP_HOST='admin.example')
        request_b = RequestFactory().get(self.change_url, secure=True, HTTP_HOST='second.example')
        fields_a = model_admin.get_readonly_fields(request_a, self.link)
        list_a = model_admin.get_list_display(request_a)
        fields_b = model_admin.get_readonly_fields(request_b, self.link)
        list_b = model_admin.get_list_display(request_b)
        for fields, listing, origin in ((fields_a, list_a, 'http://admin.example'),
                                       (fields_b, list_b, 'https://second.example')):
            for renderer in (*fields[:3], listing[2]):
                self.assertIn(origin + '/example/', renderer(self.link))

    @override_settings(SHORTLINK_BASE_URL='')
    def test_request_fallback_ignores_untrusted_forwarded_scheme_and_host(self):
        response, payloads = self.qr_response(
            HTTP_HOST='admin.example', HTTP_X_FORWARDED_PROTO='https', HTTP_X_FORWARDED_HOST='attacker.example',
        )
        self.assert_png(response)
        self.assertEqual(payloads, ['http://admin.example/example/'])

    def test_view_and_change_permissions_allow_qr_access(self):
        for user in (self.viewer, self.editor):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response, payloads = self.qr_response()
                self.assert_png(response)
                self.assertEqual(payloads, ['https://go.example/example/'])

    def test_staff_without_view_or_change_permission_cannot_generate_qr(self):
        for user in (self.staff, self.add_only):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response, payloads = self.qr_response()
                self.assertEqual(response.status_code, 403)
                self.assertEqual(payloads, [])

    def test_anonymous_nonstaff_and_inactive_users_must_log_in(self):
        for user in (None, self.nonstaff, self.inactive):
            with self.subTest(user=None if user is None else user.username):
                self.client.logout()
                if user is not None:
                    self.client.force_login(user)
                response, payloads = self.qr_response()
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('admin:login'), response['Location'])
                self.assertEqual(payloads, [])

    def test_qr_checks_the_specific_object_permission(self):
        model_admin = admin.site._registry[ShortLink]
        with patch.object(model_admin, 'has_view_or_change_permission', return_value=False) as check:
            response, payloads = self.qr_response()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(check.call_args.args[1], self.link)
        self.assertEqual(payloads, [])

    def test_missing_or_invalid_object_returns_404(self):
        for object_id in ('999999', 'not-a-number'):
            with self.subTest(object_id=object_id):
                response, payloads = self.qr_response(reverse('admin:links_shortlink_qr_code', args=[object_id]))
                self.assertEqual(response.status_code, 404)
                self.assertEqual(payloads, [])

    def test_view_only_change_page_still_shows_copy_and_qr_controls(self):
        self.client.force_login(self.viewer)
        response = self.client.get(self.change_url)
        self.assertContains(response, 'value="https://go.example/example/"')
        self.assertContains(response, f'src="{self.qr_url}"')
        self.assertNotContains(response, 'name="_save"')

    def test_add_and_change_forms_still_save_links(self):
        add_url = reverse('admin:links_shortlink_add')
        response = self.client.get(add_url)
        self.assertContains(response, 'Save first', count=3)
        response = self.client.post(add_url, {
            'short_code': 'New-Code', 'target_url': 'https://destination.example/new', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        created = ShortLink.objects.get(short_code='new-code')
        response = self.client.post(reverse('admin:links_shortlink_change', args=[created.pk]), {
            'short_code': 'new-code', 'target_url': 'https://destination.example/changed', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.target_url, 'https://destination.example/changed')
