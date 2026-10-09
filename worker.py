"""Railway job for a single read-only YouTube channel scan."""

import logging
import json
from datetime import datetime, timezone
import os
from pathlib import Path

from channel_monitor import scan_channel
from youtube_analytics import query_channel_analytics
from youtube_oauth import (
    build_youtube_analytics_client,
    build_youtube_client,
    verify_channel_access,
)


def _positive_int(name, default, minimum=1):
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc
    if value < minimum:
        raise SystemExit(f"{name} must be at least {minimum}")
    return value


def _enabled(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def run_once():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    youtube = build_youtube_client()
    verify_channel_access(youtube)
    logging.info("YouTube OAuth verified")

    max_results = _positive_int("YOUTUBE_SCAN_MAX_RESULTS", 10)
    if max_results > 50:
        raise SystemExit("YOUTUBE_SCAN_MAX_RESULTS must be at most 50")

    snapshot = scan_channel(youtube, max_results=max_results)
    logging.info(
        "Read-only YouTube scan complete: channel=%s recent_videos=%s",
        snapshot["channel_id"],
        len(snapshot["recent_videos"]),
    )

    if _enabled("YOUTUBE_ANALYTICS_ENABLED"):
        report = None
        try:
            analytics = build_youtube_analytics_client()
            report = query_channel_analytics(analytics, max_results=max_results)
        except Exception as exc:
            logging.warning("YouTube Analytics unavailable: %s", type(exc).__name__)
        report_root = Path(os.environ.get("ANALYTICS_REPORT_DIR", os.environ.get("SHORTS_OUTPUT", "/data/shorts-output"))) / "analytics"
        report_root.mkdir(parents=True, exist_ok=True)
        video_audit = [
            {
                "video_id": video.get("video_id"),
                "title": video.get("title", ""),
                "views_lifetime": video.get("views", 0),
                "title_length": len(video.get("title", "")),
                "review_needed": True,
                "note": "Check impressions, CTR and retention in YouTube Studio before changing metadata.",
            }
            for video in snapshot["recent_videos"]
        ]
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "channel_snapshot": snapshot,
            "analytics": report,
            "long_video_audit": video_audit,
        }
        target = report_root / "latest.json"
        staging = report_root / "latest.json.tmp"
        staging.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.replace(target)
        logging.info("Analytics report saved: %s", target)
        logging.info(
            "Read-only YouTube Analytics scan complete: channel_rows=%s video_rows=%s",
            len(report["channel"]) if report else 0,
            len(report["videos"]) if report else 0,
        )

    return snapshot


def main():
    if _enabled("SHORTS_ENABLED"):
        # Railway mounts volumes as root. Initialize only the configured job
        # directories, then run scanning and rendering as the image's worker.
        os.umask(0o077)
        for name in ("SHORTS_INBOX", "SHORTS_OUTPUT"):
            path = Path(os.environ[name])
            path.mkdir(parents=True, exist_ok=True)
            if os.getuid() == 0:
                os.chown(path, 10001, 10001)
        if os.getuid() == 0:
            os.setgroups([])
            os.setgid(10001)
            os.setuid(10001)
    run_once()
    if _enabled("SHORTS_ENABLED"):
        from shorts_pipeline import run_queue
        report = run_queue()
        logging.info("Shorts queue complete: previews=%s; publish=false",
                     len(report["clips"]) if report else 0)
    logging.info("Scheduled read-only scan finished safely")


if __name__ == "__main__":
    main()
