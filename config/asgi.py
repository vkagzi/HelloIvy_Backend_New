"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
from pathlib import Path

# Load environment variables from .env file FIRST
from dotenv import load_dotenv

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'

# Load .env file if it exists - override=True to ensure .env values take precedence
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

# Set DJANGO_SETTINGS_MODULE explicitly before ANY Django imports
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from django.urls import path
from utils.unified_realtime_consumer import UnifiedRealtimeConsumer

# Import feature handlers so they self-register via register_feature()
import domain_discovery.realtime_handler  # noqa: F401
import career_discovery.realtime_handler  # noqa: F401
import college_selector.realtime_handler  # noqa: F401
import utils.transcription_handler  # noqa: F401

all_websocket_patterns = [
    path('ws/voice/realtime/', UnifiedRealtimeConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(all_websocket_patterns)
    ),
})

