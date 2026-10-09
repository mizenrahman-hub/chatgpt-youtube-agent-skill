"""Opt-in import of one user-authorized YouTube video for preview-only Shorts.

Requires SHORTS_IMPORT_VIDEO_ID and SHORTS_IMPORT_ENABLED=true.
Does not publish or delete source videos. Public videos only; no cookies.
"""
import os
from pathlib import Path
import re
import subprocess

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def import_video(inbox):
    video_id = os.environ.get("SHORTS_IMPORT_VIDEO_ID", "").strip()
    if os.environ.get("SHORTS_IMPORT_ENABLED", "").lower() not in {"true", "1", "yes"}:
        return {"status": "disabled"}
    if not VIDEO_ID.fullmatch(video_id):
        raise ValueError("SHORTS_IMPORT_VIDEO_ID must be a valid 11-character video ID")
    inbox = Path(inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    completed = inbox / (video_id + ".completed")
    if completed.is_file():
        return {"status": "already_rendered", "video_id": video_id}
    video = inbox / (video_id + ".mp4")
    subtitles = inbox / (video_id + ".srt")
    if video.is_file() and subtitles.is_file():
        return {"status": "ready", "video_id": video_id}
    if video.is_file() and not subtitles.is_file():
        return {"status": "missing_subtitles", "video_id": video_id}
    # Cap network transfer and duration. No playlist, cookies or account credentials.
    command = [
        "yt-dlp", "--no-playlist", "--no-overwrites", "--no-part",
        "--max-filesize", "180M", "--match-filter", "duration <= 3600",
        "--socket-timeout", "20", "--retries", "2",
        "--write-subs", "--write-auto-subs", "--sub-langs", "tr",
        "--sub-format", "vtt/srt", "--convert-subs", "srt",
        "-f", "best[height<=720][ext=mp4]/best[height<=720]",
        "--merge-output-format", "mp4",
        "-o", str(inbox / (video_id + ".%(ext)s")),
        "https://www.youtube.com/watch?v=" + video_id,
    ]
    try:
        subprocess.run(command, check=True, timeout=900, capture_output=True, text=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"status": "download_unavailable", "video_id": video_id}
    # yt-dlp labels subtitles by language; normalize only a matching Turkish track.
    if not subtitles.exists():
        for candidate in sorted(inbox.glob(video_id + ".tr*.srt")):
            candidate.rename(subtitles)
            break
    if not video.is_file():
        return {"status": "download_unavailable", "video_id": video_id}
    if not subtitles.is_file():
        return {"status": "missing_subtitles", "video_id": video_id}
    # Only downloader-created files receive this marker; user-provided files are never cleaned.
    (inbox / (video_id + ".imported")).write_text("temporary owned-video import\n")
    return {"status": "ready", "video_id": video_id}

def cleanup_rendered_import(inbox, video_id, report, output_root):
    """Remove only marked temporary imports after every preview has been verified."""
    if not VIDEO_ID.fullmatch(video_id):
        return False
    inbox = Path(inbox)
    marker = inbox / (video_id + ".imported")
    if not marker.is_file() or not report or report.get("status") != "awaiting_review":
        return False
    clips = report.get("clips", [])
    if not clips:
        return False
    from shorts_pipeline import validate_vertical_short, probe
    import json
    output_root = Path(output_root)
    found = False
    for review_path in output_root.glob("*/review.json"):
        saved = json.loads(review_path.read_text(encoding="utf-8"))
        if saved != report:
            continue
        if all((review_path.parent / clip["file"]).is_file() for clip in clips):
            for clip in clips:
                preview = review_path.parent / clip["file"]
                validate_vertical_short(preview)
                probe(preview)
            found = True
            break
    if not found:
        return False
    # Completed marker is written first to prevent another automatic download.
    (inbox / (video_id + ".completed")).write_text("rendered preview retained\n")
    for extension in (".mp4", ".srt", ".json", ".imported"):
        (inbox / (video_id + extension)).unlink(missing_ok=True)
    return True
