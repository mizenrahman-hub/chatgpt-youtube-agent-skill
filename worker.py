"""Railway readiness scaffold. No jobs or external integrations are enabled."""

import json
import logging
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from youtube_oauth import build_youtube_client, verify_channel_access

STOP = threading.Event()
OAUTH_CONNECTED = False


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        body = json.dumps(
            {"status": "ok", "mode": "idle", "youtube_oauth": "connected" if OAUTH_CONNECTED else "not_connected"}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Do not log request paths or user-supplied values.
        pass


def request_stop(signum, frame):
    STOP.set()


def main():
    global OAUTH_CONNECTED
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        port = int(os.environ.get("PORT", "8080"))
    except ValueError:
        raise SystemExit("PORT must be an integer")
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535")

    youtube = build_youtube_client()
    verify_channel_access(youtube)
    OAUTH_CONNECTED = True
    logging.info("YouTube OAuth verified with a read-only channel lookup")

    STOP.clear()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.info("Health server listening on port %s; jobs disabled", port)
    try:
        while not STOP.wait(1):
            if not thread.is_alive():
                raise RuntimeError("Health server stopped unexpectedly")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        logging.info("Worker stopped safely")


if __name__ == "__main__":
    main()
