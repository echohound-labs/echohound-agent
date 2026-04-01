"""
utils/health.py — Simple HTTP health endpoint
Runs in a background thread. Returns {"status":"ok","uptime":X}
Check with: curl http://localhost:8080/health
"""
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

_start_time = time.time()


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({
                "status": "ok",
                "uptime_seconds": int(time.time() - _start_time),
                "uptime_human": _fmt_uptime(time.time() - _start_time),
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # suppress access logs


def _fmt_uptime(seconds: float) -> str:
    h, m, s = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60)
    return f"{h}h {m}m {s}s"


def start_health_server(port: int = 8080):
    """Start health server in a background daemon thread."""
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[Health] Server running on port {port} — curl http://localhost:{port}/health")
