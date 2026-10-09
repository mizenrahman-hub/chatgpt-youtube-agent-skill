"""Read-only preflight for German dubbing of the latest owned long video.

No synthetic audio or YouTube audio upload is claimed or performed.
"""
import json
from pathlib import Path

def latest_long_video(youtube, channel_id, report_dir):
    channel = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    items = channel.get("items", [])
    if len(items) != 1:
        raise ValueError("Authorized channel not found")
    playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    page = None
    scanned = 0
    while scanned < 250:
        response = youtube.playlistItems().list(part="contentDetails", playlistId=playlist, maxResults=50, pageToken=page).execute()
        ids = [x["contentDetails"]["videoId"] for x in response.get("items", [])]
        if ids:
            videos = youtube.videos().list(part="snippet,contentDetails", id=",".join(ids)).execute()
            by_id = {v["id"]: v for v in videos.get("items", [])}
            for video_id in ids:
                v = by_id.get(video_id)
                if not v:
                    continue
                duration = v["contentDetails"].get("duration", "")
                import re
                m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
                seconds = (int(m.group(1) or 0)*3600 + int(m.group(2) or 0)*60 + int(m.group(3) or 0)) if m else 0
                if seconds >= 240 and v["snippet"].get("liveBroadcastContent") == "none":
                    result = {"video_id": video_id, "title": v["snippet"]["title"], "duration_seconds": seconds, "language": "de", "status": "awaiting_transcript_and_audio_generation", "youtube_audio_upload": "manual_studio_step_required"}
                    root = Path(report_dir)
                    root.mkdir(parents=True, exist_ok=True)
                    dest = root / "latest_german_dub_preflight.json"
                    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                    return result
        scanned += len(ids)
        page = response.get("nextPageToken")
        if not page:
            break
    return {"status": "no_long_video_found", "scanned": scanned}
