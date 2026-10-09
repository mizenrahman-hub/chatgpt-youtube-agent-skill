"""Offline German voice-track renderer from an APPROVED German SRT.

Uses locally installed Piper CLI and voice model, plus ffmpeg. No paid APIs,
automatic translation claims, YouTube writes, or deletion of source media.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

from shorts_pipeline import read_srt


def render(srt_path: Path, model: Path, output: Path, duration: float):
    if not srt_path.is_file() or not model.is_file():
        raise ValueError("Approved German SRT and locally installed Piper voice model are required")
    if shutil.which("piper") is None or shutil.which("ffmpeg") is None:
        raise RuntimeError("Piper and ffmpeg must be installed before rendering")
    if duration <= 0 or duration > 21600:
        raise ValueError("Duration must be positive and at most 6 hours")
    cues = read_srt(srt_path)
    if not cues:
        raise ValueError("No subtitle cues")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="de-dub-") as temp_dir:
        temp = Path(temp_dir)
        inputs = []
        for i, (start, end, spoken) in enumerate(cues):
            if not spoken.strip() or start < 0 or end > duration or start >= end:
                raise ValueError("Invalid cue timing or text")
            raw = temp / f"cue_{i:04d}.wav"
            subprocess.run(["piper", "--model", str(model), "--output_file", str(raw)],
                           input=spoken, text=True, check=True, capture_output=True, timeout=120)
            with wave.open(str(raw), "rb") as wav:
                cue_duration = wav.getnframes() / wav.getframerate()
            if cue_duration > end - start + 0.05:
                raise ValueError(f"Cue {i+1} speech exceeds available slot; revise German text")
            inputs.append((raw, start))
        # Use silence as the base, then position each generated voice cue precisely.
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        for path, _ in inputs:
            command += ["-i", str(path)]
        filters = []
        labels = ["[0:a]"]
        for i, (_, start) in enumerate(inputs, 1):
            delay = round(start * 1000)
            filters.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay}|{delay}[v{i}]")
            labels.append(f"[v{i}]")
        filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0[out]")
        command += ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", str(duration),
                    "-c:a", "pcm_s16le", str(output)]
        subprocess.run(command, check=True, capture_output=True, timeout=900)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, required=True)
    args = parser.parse_args()
    print(render(args.srt, args.model, args.output, args.duration))
