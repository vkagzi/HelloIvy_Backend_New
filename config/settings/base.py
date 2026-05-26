# Resend API key (set this in your environment or .env file)
import os
from pathlib import Path
import environ

env = environ.Env()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))


SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
# ALLOWED_HOSTS is set in production.py or development.py

# Apps
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "apps.accounts",
    "apps.profiles",
    "career_discovery",
    "domain_discovery",
    "college_selector",
    "apps.locations",
    "storages",
    # "apps.brainstorm_essays",
    # "apps.evaluate_essays",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Middleware, URL config, WSGI config


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.logging.LogRequestsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]
# CORS Configuration - Use env variable for production
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=True)
CORS_ALLOW_CREDENTIALS = True

# Default local development origins
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "https://hello-ivy.vercel.app",
    "https://hello-ivy-*.vercel.app",  # Vercel preview deployments
]

# Allow override via environment variable for production
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=DEFAULT_CORS_ORIGINS)
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Channels configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# DB
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://localhost/postgres",
    ),
}

# Supabase connection options
# DATABASES['default']['OPTIONS'] = {
#     'sslmode': 'require',
#     'connect_timeout': 10,
# }

# Static & Media
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "mediafiles")

# REST
RENDERER_CLASSES = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]
REST_FRAMEWORK: dict[str, list[str] | str] = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.CustomJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "apps.accounts.permissions.RolePermission",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": RENDERER_CLASSES,
}
SPECTACULAR_SETTINGS = {
    "TITLE": "API",
    "DESCRIPTION": "API Documentation",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,  # Avoid exposing schema in production
    "COMPONENT_SPLIT_REQUEST": True,
    "AUTHENTICATION_WHITELIST": [
        "apps.accounts.authentication.CustomJWTAuthentication"
    ],
    "SECURITY": [{"Bearer": []}],
}

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# LLM Provider Configuration (azure or google)
# Default to Azure for backward compatibility
LLM_PROVIDER = env("LLM_PROVIDER", default="azure")

# Azure OpenAI Configuration for Career & Degree Selection 
# These can be set via environment variables
AZURE_OPENAI_ENDPOINT = env("AZURE_OPENAI_ENDPOINT", default=None)
AZURE_OPENAI_API_KEY = env("AZURE_OPENAI_API_KEY", default=None)
AZURE_OPENAI_DEPLOYMENT = env("AZURE_OPENAI_DEPLOYMENT", default="gpt-5.2")
AZURE_OPENAI_WHISPER_DEPLOYMENT = env("AZURE_OPENAI_WHISPER_DEPLOYMENT", default="whisper")
AZURE_OPENAI_TTS_API_KEY = env("AZURE_OPENAI_TTS_API_KEY", default=AZURE_OPENAI_API_KEY)
AZURE_OPENAI_TTS_ENDPOINT = env("AZURE_OPENAI_TTS_ENDPOINT", default=AZURE_OPENAI_ENDPOINT)
AZURE_OPENAI_TTS_DEPLOYMENT = env("AZURE_OPENAI_TTS_DEPLOYMENT", default="gpt-audio-1.5")
AZURE_OPENAI_USE_RESPONSES_API = env.bool("AZURE_OPENAI_USE_RESPONSES_API", default=True)

# Google Gemini Configuration for Career & Degree Selection 
# These can be set via environment variables
GOOGLE_API_KEY = env("GOOGLE_API_KEY", default=None)
GOOGLE_MODEL = env("GOOGLE_MODEL", default="gemini-3.0-pro-preview")

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True

# File storage – S3 (optional, falls back to local filesystem)
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default=None)
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default=None)
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default=None)
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="ap-south-1")
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default=None)
AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
AWS_QUERYSTRING_AUTH = True  # signed URLs for private files
AWS_S3_FILE_OVERWRITE = False

if AWS_STORAGE_BUCKET_NAME:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# Azure Blob Storage for media uploads (logos, etc.)
AZURE_STORAGE_CONNECTION_STRING = env("AZURE_STORAGE_CONNECTION_STRING", default="")
AZURE_STORAGE_CONTAINER_NAME = env("AZURE_STORAGE_CONTAINER_NAME", default="rilogos")

# ============================================================================
# HDFC Payment Gateway Configuration
# ============================================================================
# Payment gateway type: 'hdfc' (production) or 'dummy' (for testing)
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", default="hdfc")

# HDFC SmartGateway Configuration
# Get these credentials from: https://dashboarduat.smartgatewayuat.hdfcbank.com/settings/Security
# Documentation: https://smartgateway.hdfcbank.com/docs/smartgateway-kits-integration/web/
HDFC_MERCHANT_ID = env("HDFC_MERCHANT_ID", default="")
HDFC_PAYMENT_PAGE_CLIENT_ID = env("HDFC_PAYMENT_PAGE_CLIENT_ID", default="hdfcmaster")  # Sandbox: 'hdfcmaster'
HDFC_API_KEY = env("HDFC_API_KEY", default="")  # Generated from SmartGateway Dashboard
HDFC_RESPONSE_KEY = env("HDFC_RESPONSE_KEY", default="")  # Response verification key
HDFC_SANDBOX_MODE = env.bool("HDFC_SANDBOX_MODE", default=True)  # Set to False for production

# Note: During onboarding, production accounts are in restricted mode with:
# - Max 200 transactions per day
# - Max Rs 10 per transaction
# These restrictions are removed after QA sign-off from HDFC

# Frontend base URL — used for building HDFC return URLs
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:3000")
