from uvicorn.workers import UvicornWorker


class UvicornWorkerNoLifespan(UvicornWorker):
    """Custom Gunicorn worker that disables the ASGI lifespan protocol."""

    CONFIG_KWARGS = {"lifespan": "off"}
