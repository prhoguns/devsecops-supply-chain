import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.loadgen import hit


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
