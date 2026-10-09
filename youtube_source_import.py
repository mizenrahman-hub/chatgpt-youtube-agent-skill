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
    return {"status": "ready", "video_id": video_id}
