"""Validate private local video ingestion jobs before Shorts rendering.

This module does not download YouTube videos or publish anything.
Only files under a configured private media directory may be used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024 * 1024


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_job(job_file: Path, media_root: Path) -> dict:
    root = media_root.resolve(strict=True)
    job_path = job_file.resolve(strict=True)
    if not inside(job_path, root) or job_path.suffix.lower() != ".json":
        raise ValueError("Job JSON must be inside the private media directory")
    job = json.loads(job_path.read_text(encoding="utf-8"))
    if not isinstance(job, dict):
        raise ValueError("Job must be a JSON object")
    raw_source = job.get("source")
    if not isinstance(raw_source, str) or not raw_source.strip():
        raise ValueError("Missing local source filename")
    source = (job_path.parent / raw_source).resolve(strict=True)
    if not inside(source, root) or not source.is_file():
        raise ValueError("Source must be a local file inside private media directory")
    if source.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
        raise ValueError("Unsupported video format")
    if source.stat().st_size <= 0 or source.stat().st_size > MAX_BYTES:
        raise ValueError("Source video is empty or exceeds 10 GiB")
    subtitle = job.get("subtitles")
    if subtitle is not None:
        if not isinstance(subtitle, str):
            raise ValueError("Subtitle path must be text")
        sub_path = (job_path.parent / subtitle).resolve(strict=True)
        if not inside(sub_path, root) or not sub_path.is_file() or sub_path.suffix.lower() != ".srt":
            raise ValueError("Subtitles must be a local SRT within private media directory")
    url = job.get("long_video_url", "")
    if url and (not isinstance(url, str) or not url.startswith(("https://www.youtube.com/watch?v=", "https://youtu.be/"))):
        raise ValueError("Long video URL must be a YouTube watch link")
    return {"valid": True, "source_name": source.name, "source_bytes": source.stat().st_size,
            "has_subtitles": subtitle is not None, "publish": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", type=Path)
    parser.add_argument("--media-root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(validate_job(args.job, args.media_root), ensure_ascii=False))


if __name__ == "__main__":
    main()
