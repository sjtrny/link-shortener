import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip().lower()
    if value in {'1', 'true', 'yes', 'on'}:
        return True
    if value in {'0', 'false', 'no', 'off'}:
        return False
    raise ImproperlyConfigured(f'{name} must be True or False.')


def env_list(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, '').split(',') if value.strip()]


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured(
        'Set DJANGO_SECRET_KEY to a random secret of at least 50 characters '
        'with at least 5 distinct characters. Do not use an example key.'
    )

DEBUG = env_bool('DJANGO_DEBUG', False)
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS')
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        'Set DJANGO_ALLOWED_HOSTS to a comma-separated list of trusted hosts; "*" is not allowed.'
    )
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')
SHORTLINK_BASE_URL = os.getenv('SHORTLINK_BASE_URL', '').rstrip('/')

SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', True)
SESSION_COOKIE_SECURE = env_bool('DJANGO_SESSION_COOKIE_SECURE', True)
CSRF_COOKIE_SECURE = env_bool('DJANGO_CSRF_COOKIE_SECURE', True)
try:
    SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_SECURE_HSTS_SECONDS', '0'))
except ValueError as exc:
    raise ImproperlyConfigured('DJANGO_SECURE_HSTS_SECONDS must be a non-negative integer.') from exc
if SECURE_HSTS_SECONDS < 0:
    raise ImproperlyConfigured('DJANGO_SECURE_HSTS_SECONDS must be a non-negative integer.')
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD', False)

# Gunicorn validates the proxy's source IP before setting wsgi.url_scheme.
# Do not trust X-Forwarded-Proto directly in Django, which would bypass that check.
SECURE_PROXY_SSL_HEADER = None
USE_X_FORWARDED_HOST = False

(BASE_DIR / 'data').mkdir(exist_ok=True)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'links',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'data' / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
