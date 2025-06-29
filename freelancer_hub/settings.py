from celery.schedules import crontab
from pathlib import Path
from dotenv import load_dotenv
import os
import dj_database_url

# Load .env from project root (2 levels up from settings.py)
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)  # Explicitly specify path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Use dj-database-url to parse DATABASE_URL (add to top of settings.py)
import dj_database_url

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY set in .env file!")
# print("SECRET_KEY fetched:", SECRET_KEY)  # Debug line (remove later)
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = ['*']  # For testing; replace with your Railway domain later

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL_PRIVATE', 'redis://localhost:6379')  # Prefer private URL

# Channels (WebSocket/chat)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],  # Use Redis URL for WebSocket backend
            "capacity": 1000,      # Adjust based on expected traffic
            "expiry": 10,          # Connection lifetime (seconds)
        },
    },
}

# Celery (background tasks/notifications)
CELERY_BROKER_URL = REDIS_URL  # Use Redis as the Celery broker
CELERY_RESULT_BACKEND = REDIS_URL  # Use Redis for task results
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# Caching (optional)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",  # Optional compression
        }
    }
}

# Application definition

INSTALLED_APPS = [
    'daphne',  # Daphne for ASGI support
    'channels',
    'client',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    "django_celery_beat",
    'core',
    'chat',
    'OBSP',
    'Profile',
    'freelancer',
    'collaborations',
    'rest_framework_simplejwt',
    'projectmanagement',
    'talentrise',
    'financeapp',
    'drf_yasg',
    "corsheaders",
    'rest_framework_simplejwt.token_blacklist',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # Use default JWT Authentication
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',  # Ensure that only authenticated users can access the view
    ],
}

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_LIFETIME_MINUTES', 30))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_LIFETIME_DAYS', 1))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

CORS_ALLOWED_ORIGINS = [
    "https://talintzf.netlify.app",
]
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CSRF_TRUSTED_ORIGINS = [
    'https://talintzbackend-production.up.railway.app',
    'https://*.railway.app'
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'freelancer_hub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'freelancer_hub.wsgi.application'
ASGI_APPLICATION = "freelancer_hub.asgi.application"

CELERY_BEAT_SCHEDULE = {
    'check-deadlines-every-day': {
        'task': 'client.tasks.check_deadlines',  # Task path
        'schedule': crontab(minute=0, hour=0),  # Runs every day at midnight
    },
    'check-events-every-minute': {
        'task': 'client.tasks.send_event_approaching_notification',  # Make sure this path is correct
        'schedule': 30.0,  # Run every minute (adjust as needed)
    },
}

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',  # This should remain here for custom User model
)

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'  # URL prefix for media files (accessible to the browser)
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # Path where media files are stored on the server

FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

ASGI_APPLICATION = 'freelancer_hub.asgi.application'

AUTH_USER_MODEL = 'core.User'

# Add to your settings
ADMIN_SITE_HEADER = "Talintz Admin"
ADMIN_SITE_TITLE = "Talintz Admin Portal"
ADMIN_INDEX_TITLE = "Welcome to Talintz Administration"

RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Critical security settings (add to production.py)
SECURE_HSTS_SECONDS = 2592000  # 30 days in seconds
SECURE_SSL_REDIRECT = False    # Disable SSL redirect for development
SESSION_COOKIE_SECURE = False  # Disable secure cookies for development
CSRF_COOKIE_SECURE = False     # Disable secure CSRF cookies for development

# Hardcoded private PostgreSQL URL (recommended for Railway)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'shortline.proxy.rlwy.net',  # Private host
        'PORT': '18928',                       # Default PostgreSQL port
        'NAME': os.getenv('PGDATABASE'),      # Database name (from env)
        'USER': os.getenv('PGUSER'),          # Username (from env)
        'PASSWORD': os.getenv('PGPASSWORD'),  # Password (from env)
    }
}
