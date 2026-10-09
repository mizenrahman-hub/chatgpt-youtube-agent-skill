"""Download Turkish caption track for an owned public long video, without video media.

Opt-in helper. Never downloads private videos, publishes or edits YouTube.
"""
import argparse
from pathlib import Path
import re
import subprocess

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

def fetch_turkish_captions(video_id, output_dir):
    if not VIDEO_ID.fullmatch(video_id):
        raise ValueError("Invalid YouTube video ID")
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / (video_id + ".tr.srt")
    if dest.exists() and dest.stat().st_size:
        return {"status": "ready", "path": str(dest)}
    args = ["yt-dlp", "--skip-download", "--no-playlist", "--write-subs",
            "--write-auto-subs", "--sub-langs", "tr", "--sub-format", "srt/vtt",
            "--convert-subs", "srt", "-o", str(root / (video_id + ".%(ext)s")),
            "https://www.youtube.com/watch?v=" + video_id]
    try:
        subprocess.run(args, check=True, capture_output=True, text=True, timeout=180)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"status": "captions_unavailable", "video_id": video_id}
    for path in root.glob(video_id + ".tr*.srt"):
        if path.stat().st_size:
            if path != dest:
                path.rename(dest)
            return {"status": "ready", "path": str(dest)}
    return {"status": "captions_unavailable", "video_id": video_id}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--video-id", required=True)
    p.add_argument("--output-dir", default="/data/german-dub")
    a = p.parse_args()
    print(fetch_turkish_captions(a.video_id, a.output_dir))
