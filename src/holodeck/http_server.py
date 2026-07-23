from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer
from socketserver import BaseServer

REQUEST_TIMEOUT_SECONDS = 30
MAX_CONCURRENT_REQUESTS = 64
_CAPACITY_BODY = b'{"error":"server is at capacity"}'
_CAPACITY_RESPONSE = (
    b"HTTP/1.1 503 Service Unavailable\r\n"
    b"Content-Type: application/json\r\n"
    b"Content-Length: " + str(len(_CAPACITY_BODY)).encode("ascii") + b"\r\n"
    b"Connection: close\r\n\r\n" + _CAPACITY_BODY
)


class HolodeckHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server with bounded concurrency and socket timeouts."""

    daemon_threads = True
    request_queue_size = 8

    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type,
        *,
        request_timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
        max_concurrent_requests: int = MAX_CONCURRENT_REQUESTS,
    ) -> None:
        super().__init__(server_address, RequestHandlerClass)
        self.request_timeout_seconds = request_timeout_seconds
        self._workers = threading.BoundedSemaphore(max_concurrent_requests)

    def get_request(self) -> tuple[object, object]:
        conn, client_address = super().get_request()
        conn.settimeout(self.request_timeout_seconds)
        return conn, client_address

    def process_request(self, request: object, client_address: object) -> None:
        if not self._workers.acquire(blocking=False):
            self._reject_at_capacity(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request: object, client_address: object) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._workers.release()

    @staticmethod
    def _reject_at_capacity(request: object) -> None:
        try:
            request.sendall(_CAPACITY_RESPONSE)
        except OSError:
            pass
        finally:
            request.close()


def create_http_server(
    bind_address: tuple[str, int],
    handler: type,
    *,
    request_timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
    max_concurrent_requests: int = MAX_CONCURRENT_REQUESTS,
) -> BaseServer:
    return HolodeckHTTPServer(
        bind_address,
        handler,
        request_timeout_seconds=request_timeout_seconds,
        max_concurrent_requests=max_concurrent_requests,
    )
