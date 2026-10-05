"""Local, preview-only Shorts jobs. No YouTube writes or source downloads."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent


def probe(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(path)], check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    if not any(s["codec_type"] == "video" for s in data["streams"]):
        raise ValueError("Source has no video stream")
    return float(data["format"]["duration"])


def read_srt(path):
    def seconds(value):
        h, m, s = value.replace(",", ".").split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    rows = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        timing = next((i for i, line in enumerate(lines) if " --> " in line), None)
        if timing is None:
            continue
        start, end = lines[timing].split(" --> ")
        rows.append((seconds(start), seconds(end), " ".join(lines[timing + 1:])))
    return rows


def stamp(seconds):
    ms = round(max(0, seconds) * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def clipped_srt(rows, start, end):
    selected = [(max(0, a-start), min(end, b)-start, text)
                for a, b, text in rows if b > start and a < end]
    return "\n\n".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n{text}"
                       for i, (a, b, text) in enumerate(selected, 1)) + "\n"


def candidates(rows, duration, limit=3):
    """Transcript keyword heuristic, not a retention or visual quality judgment."""
    keywords = ("kim var", "kork", "ses", "tehlike", "inanam", "şelale", "mağara", "ilk kez")
    ranked = []
    for a, b, text in rows:
        score = sum(word in text.lower() for word in keywords)
        if score and duration - a >= 15:
            start = max(0, a - 2)
            ranked.append((score, start, min(duration, start + 35), text))
    selected = []
    for score, start, end, text in sorted(ranked, key=lambda row: (-row[0], row[1])):
        if any(start < c["end"] and end > c["start"] for c in selected):
            continue
        selected.append({"start": start, "end": end, "reason": text,
                         "selection": "transcript_keyword_heuristic", "score": score})
        if len(selected) == limit:
            break
    return selected


def run_job(job_path, output_root, render=False):
    job_path = Path(job_path).resolve()
    job = json.loads(job_path.read_text(encoding="utf-8"))
    source = (job_path.parent / job["source"]).resolve()
    if not source.is_file():
        raise ValueError("Original video file is required")
    duration = probe(source)
    subtitle_path = (job_path.parent / job["subtitles"]).resolve() if job.get("subtitles") else None
    rows = read_srt(subtitle_path) if subtitle_path else []
    clips = job.get("clips")
    if clips is None:
        clips = candidates(rows, duration)
    if not clips or len(clips) > 3:
        raise ValueError("Provide 1-3 clips or an SRT with matching candidate moments")
    for clip in clips:
        a, b = float(clip["start"]), float(clip["end"])
        if not all(map(math.isfinite, (a, b))) or not (0 <= a < b <= duration) or not (15 <= b-a <= 60):
            raise ValueError("Each clip must be within the source and last 15-60 seconds")
    # Include source and subtitle contents so edits cannot reuse stale previews.
    digest = hashlib.sha256(job_path.read_bytes())
    for path in (source, subtitle_path):
        if path:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024*1024), b""):
                    digest.update(chunk)
    output = Path(output_root).resolve() / digest.hexdigest()[:24]
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "review.json"
    if report_path.exists():
        existing = json.loads(report_path.read_text())
        if existing.get("status") == "awaiting_review" and all((output / c["file"]).is_file() for c in existing["clips"]):
            return existing
    report = {"status": "planned", "publish": False, "source_deleted": False,
              "source_title": job.get("title", ""), "long_video_url": job.get("long_video_url", ""),
              "selection_note": "Candidates need human review; no retention or scene analysis implied.",
              "clips": []}
    for index, clip in enumerate(clips, 1):
        filename = f"short-{index}.mp4"
        entry = dict(clip, file=filename, title=clip.get("title", job.get("title", "")),
                     description=f"Uzun videonun tamamı: {job.get('long_video_url', '')}",
                     hashtags=job.get("hashtags", ["#Shorts", "#RamyYollarda"]))
        report["clips"].append(entry)
        if not render:
            continue
        with tempfile.TemporaryDirectory(prefix="shorts-") as temp:
            temp = Path(temp)
            filters = ["scale=1080:1920:force_original_aspect_ratio=increase", "crop=1080:1920", "setsar=1"]
            caption = clipped_srt(rows, float(clip["start"]), float(clip["end"]))
            if rows and caption.strip():
                (temp / "captions.srt").write_text(caption, encoding="utf-8")
                filters.append("subtitles=captions.srt:force_style='FontName=DejaVu Sans,FontSize=18,Outline=2,MarginV=100'")
            if clip.get("hook"):
                (temp / "hook.txt").write_text(str(clip["hook"]), encoding="utf-8")
                filters.append("drawtext=textfile=hook.txt:expansion=none:fontcolor=white:fontsize=48:box=1:boxcolor=black@0.6:x=(w-text_w)/2:y=160:enable='lt(t,3)'")
            pending = temp / "preview.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", str(clip["start"]),
                            "-i", str(source), "-t", str(float(clip["end"])-float(clip["start"])),
                            "-map", "0:v:0", "-map", "0:a:0?", "-vf", ",".join(filters),
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-movflags", "+faststart", str(pending)],
                           cwd=temp, check=True, timeout=600)
            probe(pending)
            # Copy through a sibling temporary file before the atomic rename.
            import shutil
            staging = output / (filename + ".tmp")
            shutil.copyfile(pending, staging)
            staging.replace(output / filename)
    report["status"] = "awaiting_review" if render else "planned"
    staging = output / "review.json.tmp"
    staging.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    staging.replace(report_path)
    return report


def run_queue():
    inbox = Path(os.environ["SHORTS_INBOX"])
    output = Path(os.environ["SHORTS_OUTPUT"])
    if not inbox.is_dir():
        raise ValueError("SHORTS_INBOX must be an existing directory")
    # One job per run bounds CPU usage. Completed jobs are skipped on later runs.
    for path in sorted(inbox.glob("*.json")):
        report = run_job(path, output, render=False)
        if report["status"] == "planned":
            rendered = run_job(path, output, render=True)
            return rendered
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_job(args.job, args.output, args.render), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
