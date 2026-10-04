---
name: yt-shorts
description: >-
  Find self-contained Shorts inside a long video, create Turkish subtitles,
  and render a person-tracked 9:16 preview. Use for "cut this into shorts",
  "clip this", "repurpose this video", or "what should I clip".
---

# yt-shorts

A useful Short must survive without the long video around it. Work preview-first and never publish,
schedule, overwrite, or delete content.

## Pick the moment

Read the transcript and rank five spans of 20-55 seconds. Each must open on a complete thought,
contain a turn or payoff, and end cleanly. Show timecodes and first lines, then wait for the creator's
choice.

## Prepare the package

For the selected span provide:

- a replacement first line that works without prior context;
- different on-screen text for the first two seconds;
- a loop point;
- a vertical-framing warning when important scenery will be cropped.

## Render a private preview

Install dependencies from `requirements.txt`; `ffmpeg` must also be available.

```bash
python scripts/transcribe_tr.py input.mp4 --output captions.tr.srt
python scripts/render_short.py input.mp4 preview.mp4 --start 30 --duration 45 \
  --subtitles captions.tr.srt
```

The second command is a dry run by default. After the creator approves the plan, repeat it with
`--render`. The renderer follows the largest detected face horizontally with smoothing instead of
using a fixed center crop. If detection is temporarily lost, it holds the last safe position.

## Approval gate

Show the resulting preview and ask: **Yayın için onaylıyor musun, yoksa değiştirelim mi?**

Do not add upload or deletion commands. Read `SAFETY.md` before changing the scripts.
