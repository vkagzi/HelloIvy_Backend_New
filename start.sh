#!/bin/bash
set -e

# Change to the Django app directory
cd helloivy-api-main

# Run migrations with verbose output and run all apps
python manage.py migrate --noinput --run-syncdb

# Collect static files
python manage.py collectstatic --noinput

# Start gunicorn with sync worker for WSGI
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 120 --worker-class sync
