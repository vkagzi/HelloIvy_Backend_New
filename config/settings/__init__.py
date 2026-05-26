import os

# Load settings based on the ENVIRONMENT variable
environment = os.getenv("DJANGO_ENV", "local")

if environment == "production":
    from .production import *
else:
    from .local import *
