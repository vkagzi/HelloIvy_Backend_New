import os
from .base import *  # pylint: disable=wildcard-import,unused-wildcard-import

DEBUG = env.bool("DEBUG", default=False)
# Allow Render, Vercel domains and common hosts
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[
    "hello-ivy.onrender.com",
    ".onrender.com",
    ".vercel.app",
    "localhost",
    "127.0.0.1",
])

# CORS - Explicitly allow all origins in production
CORS_ALLOW_ALL_ORIGINS = True
CORS_ORIGIN_ALLOW_ALL = True  # Legacy setting for older versions
CORS_ALLOW_CREDENTIALS = True
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
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]

# Static & Media Files for Production with WhiteNoise
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = "/static/"
MEDIA_ROOT = os.path.join(BASE_DIR, "mediafiles")
MEDIA_URL = "/media/"

# WhiteNoise configuration
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Security Settings (only enforce in production when HTTPS is available)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=False)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HSTS settings (only enable when HTTPS is configured)
if env.bool("ENABLE_HSTS", default=False):
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Database Connection Pooling
DATABASES['default']['CONN_MAX_AGE'] = env.int("DB_CONN_MAX_AGE", default=600)

# Logging Configuration - Console only for cloud deployment
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': env("DJANGO_LOG_LEVEL", default='INFO'),
            'propagate': False,
        },
    },
}

# Channel Layers - Use Redis in production if REDIS_URL is provided
if env("REDIS_URL", default=None):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [env("REDIS_URL")],
            },
        },
    }
