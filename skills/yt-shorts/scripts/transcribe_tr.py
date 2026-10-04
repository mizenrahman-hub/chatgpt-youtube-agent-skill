#!/usr/bin/env python3
"""Create Turkish SRT subtitles locally with faster-whisper."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def stamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Videodan Türkçe SRT altyazı üretir.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", default="small", help="Whisper model adı (varsayılan: small)")
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"Girdi bulunamadı: {args.input}")

    try:
        from faster_whisper import WhisperModel
        import numpy as np
    except ImportError as exc:
        raise SystemExit("Eksik paket: pip install faster-whisper") from exc

    output = args.output or args.input.with_suffix(".tr.srt")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("Gerekli program bulunamadı: ffmpeg")
    decoded = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(args.input), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    audio = np.frombuffer(decoded, dtype=np.float32)
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio, language="tr", vad_filter=True)

    with output.open("w", encoding="utf-8") as handle:
        for index, segment in enumerate(segments, start=1):
            handle.write(f"{index}\n{stamp(segment.start)} --> {stamp(segment.end)}\n")
            handle.write(segment.text.strip() + "\n\n")

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
