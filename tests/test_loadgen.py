import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.loadgen import hit, validate_url


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(503 if self.path == "/fail" else 200)
        self.end_headers()

    def log_message(self, *args):
        pass


def test_hit_reports_status_codes_and_connection_errors():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        assert hit(f"{base}/ok") == 200
        assert hit(f"{base}/fail") == 503
    finally:
        server.shutdown()
        server.server_close()
    assert hit(base, timeout=0.5) == 0  # nothing listening any more


def test_hit_survives_a_connection_reset():
    # A server that accepts the connection and immediately resets it, like a pod being replaced.
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()

    def reset_one():
        conn, _ = listener.accept()
        # SO_LINGER on with a 0s timeout makes close() send a TCP RST instead of a FIN.
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        conn.close()

    threading.Thread(target=reset_one, daemon=True).start()
    try:
        assert hit(f"http://127.0.0.1:{listener.getsockname()[1]}/", timeout=2) == 0
    finally:
        listener.close()


@pytest.mark.parametrize("url", ["http://demo-api/api/work", "https://example.com/x"])
def test_validate_url_accepts_http_and_https(url):
    assert validate_url(url) == url


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://host/file", "demo-api/api/work", "http://"]
)
def test_validate_url_rejects_other_schemes(url):
    with pytest.raises(ValueError):
        validate_url(url)
