# gunicorn.conf.py

worker_class = (  # pylint: disable=invalid-name
    "gunicorn_custom_workers.UvicornWorkerNoLifespan"
)
workers = 1  # pylint: disable=invalid-name
timeout = 300  # pylint: disable=invalid-name
bind = "0.0.0.0:8000"  # pylint: disable=invalid-name
keep_alive = 5  # pylint: disable=invalid-name

# Logging configuration
loglevel = 'info'  # pylint: disable=invalid-name
accesslog = '-'  # Log to stdout
errorlog = '-'  # Log to stderr
capture_output = True  # Capture stdout/stderr from application
