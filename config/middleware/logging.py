# webapi/middleware/logging.py

import logging
import time
from typing import Callable
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse

logger = logging.getLogger("django.server")  # Use Django's HTTP logger


class LogRequestsMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start_time = time.time()

        response = self.get_response(request)
        elapsed_time = (time.time() - start_time) * 1000

        # Calculate response size (content length)
        if "Content-Length" in response.headers:
            response_size_bytes = int(response.headers["Content-Length"])
        elif isinstance(response, StreamingHttpResponse):
            response_size_bytes = 0
        else:
            response_size_bytes = len(response.content) if response.content else 0

        # response size in KB rounded
        response_size = round(response_size_bytes / 1024, 2)

        # Log request details
        logger.info(
            # method status url time size
            "%s %s %s %s %s",
            request.method,
            response.status_code,
            request.get_full_path(),
            f"{elapsed_time:.2f}ms",
            f"{response_size}KB",
        )

        return response
