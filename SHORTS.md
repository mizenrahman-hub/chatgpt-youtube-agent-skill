# Preview-only Shorts pipeline

The pipeline renders 1–3 local MP4 previews at 1080×1920, 15–60 seconds each,
with source audio, optional Turkish SRT captions, an optional three-second hook,
and a review.json containing titles, descriptions and hashtags. It never uploads,
deletes, or edits a YouTube video. The default framing is a center crop; review
whether the subject stays visible. The existing face tracking renderer remains
available separately.

Create a private job JSON next to the original video:

```json
{
  "source": "original.mp4",
  "title": "Mağarada 24 saat",
  "long_video_url": "https://www.youtube.com/watch?v=YOUR_VIDEO_ID",
  "subtitles": "original.tr.srt",
  "clips": [
    {"start": 120, "end": 150, "hook": "Bu ses nereden geliyor?", "title": "Mağarada duyduğum ses"}
  ]
}
```

Omit subtitles if unavailable. Generate them with the existing
`skills/yt-shorts/scripts/transcribe_tr.py` (Whisper model download and CPU use
required). SRT timestamps refer to the full source; the pipeline rebases them for
each clip. If clips are omitted, SRT keyword matches propose up to three
nonoverlapping moments. This is a basic transcript heuristic, not visual,
retention, or storytelling analysis. No matching moments results in an error
instead of arbitrary clips.

```bash
python shorts_pipeline.py /data/inbox/job.json --output /data/previews
python shorts_pipeline.py /data/inbox/job.json --output /data/previews --render
```

The first command plans; the second renders. Completed identical jobs are reused;
job, video, or subtitle changes create a new output directory. Original video
files are required: a YouTube watch URL is metadata, not a downloadable source.
Do not commit videos, private jobs, or generated previews to the public repo.

## Railway

Disabled by default. Before enabling, use a persistent volume writable by UID
10001 for original files, private job JSONs, and previews. The current production
service has no volume. Set `SHORTS_ENABLED=true`, `SHORTS_INBOX=/data/inbox`, and
`SHORTS_OUTPUT=/data/previews` only after provisioning files and storage.
The existing cron processes at most one unfinished job per run. A bad job fails
the run and remains available for correction. There is no automatic file transfer,
preview delivery, transcription, or publication. Local previews must be reviewed
before any separate upload workflow. Rendering consumes Railway CPU/disk and is
not guaranteed free. No storage is provisioned by this code change.
