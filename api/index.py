"""
Vercel Serverless Function Entry Point for Django
"""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
os.environ.setdefault("DJANGO_ENV", "production")

# Initialize Django BEFORE importing get_wsgi_application
import django
django.setup()

from django.core.wsgi import get_wsgi_application

# Create the WSGI application
app = get_wsgi_application()

# Alias for Vercel
application = app

