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

    logging.info("Automation flags: analytics=%s discovery=%s comment_drafts=%s shorts=%s shorts_import=%s youtube_write=%s", *(_enabled(name) for name in ("YOUTUBE_ANALYTICS_ENABLED", "LONG_VIDEO_DISCOVERY_ENABLED", "COMMENT_DRAFTS_ENABLED", "SHORTS_ENABLED", "SHORTS_IMPORT_ENABLED", "YOUTUBE_WRITE_ENABLED")))

    if _enabled("YOUTUBE_ANALYTICS_ENABLED"):
        report = None
        report_7d = None
        try:
            analytics = build_youtube_analytics_client()
            report = query_channel_analytics(analytics, max_results=max_results)
            report_7d = query_channel_analytics(analytics, days=7, max_results=max_results)
        except Exception as exc:
            logging.warning("YouTube Analytics unavailable: %s", type(exc).__name__)
        report_root = Path(os.environ.get("ANALYTICS_REPORT_DIR", os.environ.get("SHORTS_OUTPUT", "/data/shorts-output"))) / "analytics"
        report_root.mkdir(parents=True, exist_ok=True)
        from long_video_seo_audit import audit_videos
        video_audit = audit_videos(snapshot["recent_videos"], report["videos"] if report else [])
        legacy_video_audit = [
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
            "analytics_7d": report_7d,
            "revenue_status": "Not available: requires YouTube Analytics monetary read-only scope and verified monetization access",
            "long_video_audit": video_audit,
        }
        target = report_root / "latest.json"
        staging = report_root / "latest.json.tmp"
        staging.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.replace(target)
        logging.info("Analytics report saved: %s", target)
        logging.info("Analytics availability: 28d=%s 7d=%s revenue=not_configured", bool(report), bool(report_7d))
        logging.info(
            "Read-only YouTube Analytics scan complete: channel_rows=%s video_rows=%s",
            len(report["channel"]) if report else 0,
            len(report["videos"]) if report else 0,
        )

    if _enabled("LONG_VIDEO_DISCOVERY_ENABLED"):
        try:
            from long_video_discovery import discover_long_videos
            root = Path(os.environ.get("ANALYTICS_REPORT_DIR", "/data/shorts-output")) / "analytics"
            discovered = discover_long_videos(youtube, snapshot["channel_id"], root)
            logging.info("Long video discovery: total=%s target_matches=%s report=%s", discovered["long_video_count"], discovered["matches"], discovered["path"])
        except Exception as exc:
            logging.warning("Long video discovery unavailable: %s", type(exc).__name__)

    if _enabled("GERMAN_DUB_PREFLIGHT_ENABLED"):
        try:
            from german_dub_preflight import latest_long_video
            from german_dub_transcript import fetch_turkish_captions
            report_dir = Path(os.environ.get("SHORTS_OUTPUT", "/data/shorts-output")) / "german-dub"
            latest = latest_long_video(youtube, snapshot["channel_id"], report_dir)
            if latest.get("video_id"):
                captions = fetch_turkish_captions(latest["video_id"], report_dir)
                logging.info("German dubbing preflight: video_id=%s captions=%s audio=not_generated upload=false", latest["video_id"], captions["status"])
            else:
                logging.info("German dubbing preflight: %s", latest["status"])
        except Exception as exc:
            logging.warning("German dubbing preflight failed: %s", type(exc).__name__)

    if _enabled("COMMENT_DRAFTS_ENABLED"):
        try:
            from comment_reply_drafts import collect_drafts
            draft_dir = Path(os.environ.get("COMMENT_DRAFTS_DIR", "/data/comment-drafts"))
            result = collect_drafts(youtube, snapshot["channel_id"], draft_dir)
            logging.info("Comment reply drafts: new=%s total=%s publish=false",
                         result["new_drafts"], result["total_drafts"])
        except Exception as exc:
            logging.warning("Comment draft scan unavailable: %s", type(exc).__name__)

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
        if _enabled("SHORTS_IMPORT_ENABLED"):
            from youtube_source_import import import_video
            import_result = import_video(Path(os.environ["SHORTS_INBOX"]))
            logging.info("Owned YouTube source import: status=%s", import_result["status"])
        from shorts_pipeline import queue_diagnostics, run_queue
        inbox = Path(os.environ["SHORTS_INBOX"])
        before = queue_diagnostics(inbox)
        logging.info("Shorts input readiness: sources=%s paired_srt=%s missing_srt=%s jobs=%s",
                     before["source_videos"], before["videos_with_srt"],
                     before["videos_missing_srt"], before["queued_jobs"])
        report = run_queue()
        logging.info("Shorts queue complete: previews=%s; publish=false",
                     len(report["clips"]) if report else 0)
    logging.info("Scheduled read-only scan finished safely")


if __name__ == "__main__":
    main()
