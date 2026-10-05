"""Railway worker with read-only YouTube monitoring and health reporting."""

import json
import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from channel_monitor import scan_channel
from youtube_oauth import build_youtube_client, verify_channel_access

STOP = threading.Event()
OAUTH_CONNECTED = False
MONITOR_STATE = {
    "enabled": False,
    "last_scan_at": None,
    "last_scan_ok": None,
    "recent_video_count": 0,
}


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        body = json.dumps({
            "status": "ok",
            "mode": "read_only_monitor" if MONITOR_STATE["enabled"] else "idle",
            "youtube_oauth": "connected" if OAUTH_CONNECTED else "not_connected",
            "monitor": MONITOR_STATE,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def request_stop(signum, frame):
    STOP.set()


def _positive_int(name, default, minimum=1):
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc
    if value < minimum:
        raise SystemExit(f"{name} must be at least {minimum}")
    return value


def _monitor_loop(youtube, interval_seconds, max_results):
    MONITOR_STATE["enabled"] = True
    while not STOP.is_set():
        try:
            snapshot = scan_channel(youtube, max_results=max_results)
            MONITOR_STATE.update({
                "last_scan_at": snapshot["scanned_at"],
                "last_scan_ok": True,
                "recent_video_count": len(snapshot["recent_videos"]),
            })
            logging.info(
                "Read-only YouTube scan complete: channel=%s recent_videos=%s",
                snapshot["channel_id"],
                len(snapshot["recent_videos"]),
            )
        except Exception:
            MONITOR_STATE["last_scan_ok"] = False
            logging.exception("Read-only YouTube scan failed")
        if STOP.wait(interval_seconds):
            break


def main():
    global OAUTH_CONNECTED
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    port = _positive_int("PORT", 8080)
    if port > 65535:
        raise SystemExit("PORT must be between 1 and 65535")

    youtube = build_youtube_client()
    verify_channel_access(youtube)
    OAUTH_CONNECTED = True
    logging.info("YouTube OAuth verified")

    interval = _positive_int("YOUTUBE_SCAN_INTERVAL_SECONDS", 21600, 300)
    max_results = _positive_int("YOUTUBE_SCAN_MAX_RESULTS", 10)
    if max_results > 50:
        raise SystemExit("YOUTUBE_SCAN_MAX_RESULTS must be at most 50")

    STOP.clear()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    server.daemon_threads = True
    health_thread = threading.Thread(target=server.serve_forever, daemon=True)
    health_thread.start()

    monitor_thread = threading.Thread(
        target=_monitor_loop, args=(youtube, interval, max_results), daemon=True
    )
    monitor_thread.start()
    logging.info("Health server listening on port %s; read-only monitoring enabled", port)

    try:
        while not STOP.wait(1):
            if not health_thread.is_alive() or not monitor_thread.is_alive():
                raise RuntimeError("Worker thread stopped unexpectedly")
    finally:
        STOP.set()
        server.shutdown()
        server.server_close()
        health_thread.join(timeout=5)
        monitor_thread.join(timeout=5)
        logging.info("Worker stopped safely")


if __name__ == "__main__":
    main()
