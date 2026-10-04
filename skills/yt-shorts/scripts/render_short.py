#!/usr/bin/env python3
"""Render a 9:16 preview that follows the largest detected face.

The command never uploads or deletes anything. Without --render it only prints
the proposed operation, making preview-first the default behavior.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kişiyi takip eden 9:16 Shorts önizlemesi üretir.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--subtitles", type=Path)
    parser.add_argument("--render", action="store_true", help="Planı gerçekten render et")
    return parser.parse_args()


def require_program(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"Gerekli program bulunamadı: {name}")
    return path


def escape_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Girdi bulunamadı: {args.input}")
    if args.duration <= 0 or args.duration > 60:
        raise SystemExit("Shorts süresi 0-60 saniye arasında olmalı.")

    plan = {
        "input": str(args.input),
        "output": str(args.output),
        "start": args.start,
        "duration": args.duration,
        "format": "1080x1920 (9:16)",
        "tracking": "largest-face + smoothed horizontal follow",
        "subtitles": str(args.subtitles) if args.subtitles else None,
        "publish": False,
        "delete_source": False,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.render:
        print("Önizleme planı hazır. Render için --render ekleyin.")
        return 0

    try:
        import cv2
    except ImportError as exc:
        raise SystemExit("Eksik paket: pip install opencv-python-headless") from exc

    ffmpeg = require_program("ffmpeg")
    capture = cv2.VideoCapture(str(args.input))
    if not capture.isOpened():
        raise SystemExit("Video açılamadı.")

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    crop_width = min(width, int(height * 9 / 16))
    first_frame = max(0, int(args.start * fps))
    frame_count = int(args.duration * fps)
    capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame)

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    center_x = width / 2
    detect_every = max(1, round(fps / 10))
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ytshort-") as tmp:
        silent = Path(tmp) / "silent.mp4"
        writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1080, 1920))
        if not writer.isOpened():
            raise SystemExit("Geçici video yazıcısı açılamadı.")

        for index in range(frame_count):
            ok, frame = capture.read()
            if not ok:
                break
            if index % detect_every == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
                if len(faces):
                    x, _, w, _ = max(faces, key=lambda face: face[2] * face[3])
                    target = x + w / 2
                    center_x = center_x * 0.82 + target * 0.18

            left = int(max(0, min(width - crop_width, center_x - crop_width / 2)))
            cropped = frame[:, left : left + crop_width]
            writer.write(cv2.resize(cropped, (1080, 1920), interpolation=cv2.INTER_AREA))

        writer.release()
        capture.release()

        command = [
            ffmpeg, "-y", "-i", str(silent), "-ss", str(args.start), "-t", str(args.duration),
            "-i", str(args.input), "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "libx264",
            "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-shortest",
        ]
        if args.subtitles:
            if not args.subtitles.is_file():
                raise SystemExit(f"Altyazı bulunamadı: {args.subtitles}")
            command += ["-vf", f"subtitles='{escape_filter_path(args.subtitles)}':force_style='Alignment=2,FontSize=18,Outline=2,MarginV=120'"]
        command.append(str(args.output))
        subprocess.run(command, check=True)

    print(f"Önizleme hazır: {args.output}")
    print("Yayınlanmadı. Kaynak video silinmedi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
