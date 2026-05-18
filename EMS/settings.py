"""
Django settings for EMS project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=None):
    raw = os.environ.get(name)
    if raw is None:
        return default if default is not None else []
    return [item.strip() for item in raw.split(',') if item.strip()]


SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-h5b_mc-f5074tjo&)b4ah&i@h!jdbz#u&k+u-f3t_j%e+82*sh')
DEBUG = env_bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', ['localhost', '127.0.0.1'])

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:5174',
    'http://127.0.0.1:5174',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
CSRF_TRUSTED_ORIGINS += env_list('DJANGO_CSRF_TRUSTED_ORIGINS', [])

INSTALLED_APPS = [
    'daphne',  # Must be at the top for Channels to handle runserver
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for password reset
    'channels',  # Django Channels for WebSockets
    'EMSwebsite',
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
    'EMSwebsite.middleware.NoCacheMiddleware',  # Add no-cache middleware for development
]

ROOT_URLCONF = 'EMS.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'EMSwebsite.context_processors.user_role_context',
                'EMSwebsite.context_processors.get_notifications',
                'EMSwebsite.context_processors.system_settings_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'EMS.wsgi.application'
ASGI_APPLICATION = 'EMS.asgi.application'

# Django Channels Configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',  # For development
        # For production, use Redis:
        # 'BACKEND': 'channels_redis.core.RedisChannelLayer',
        # 'CONFIG': {
        #     "hosts": [('127.0.0.1', 6379)],
        # },
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'postgres'),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', ''),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',
            'options': '-c statement_timeout=60000',
        },
    }
}

# SQLite (disabled — using Supabase PostgreSQL)
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'hr_system',
#         'USER': 'hr_system',
#         'PASSWORD': 'Funtechblue.1199',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# -----------------------------------------------------------
# ✅ CACHE CONTROL SETTINGS
# -----------------------------------------------------------
# Disable caching in development mode
if DEBUG:
    # Disable WhiteNoise caching in development
    WHITENOISE_MAX_AGE = 0
    # Use dummy cache (no caching)
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
else:
    # Production: Enable caching with reasonable max age
    WHITENOISE_MAX_AGE = 31536000  # 1 year for static files
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }


# -----------------------------------------------------------
# ✅ REAL EMAIL CONFIGURATION (GMAIL SMTP)
# -----------------------------------------------------------
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'iqkhan768@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'jwap sgqj mqlm uzgx')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Employee Information System <iqkhan768@gmail.com>')

# -----------------------------------------------------------
# ✅ PASSWORD RESET SETTINGS
# -----------------------------------------------------------
PASSWORD_RESET_TIMEOUT = 86400  # 24 hours (in seconds)
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
LOGIN_URL = '/login/'

# Site ID for Django sites framework (required for password reset)
SITE_ID = 1


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -----------------------------------------------------------
# CSRF / Session cookie settings for development (Vite dev server proxy)
# -----------------------------------------------------------
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False   # JS must be able to read csrftoken cookie
CSRF_COOKIE_SECURE = False     # HTTP is fine in local dev
