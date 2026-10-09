"""Find long videos in the authenticated channel without paid vidIQ credits.

Read-only: uploads playlist + batched videos.list; no search.list (100-unit call).
"""
from __future__ import annotations
import json
from pathlib import Path
from long_video_seo_audit import audit_videos, duration_seconds

def discover_long_videos(youtube, channel_id, output_dir, max_pages=10):
    channel = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    items = channel.get("items", [])
    if len(items) != 1:
        raise RuntimeError("Authorized channel not found")
    playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    videos = []
    token = None
    for _ in range(max_pages):
        kwargs = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if token:
            kwargs["pageToken"] = token
        page = youtube.playlistItems().list(**kwargs).execute()
        ids = [x.get("contentDetails", {}).get("videoId") for x in page.get("items", [])]
        ids = [x for x in ids if x]
        if ids:
            details = youtube.videos().list(part="snippet,contentDetails,statistics", id=",".join(ids)).execute()
            for v in details.get("items", []):
                snippet = v.get("snippet", {})
                seconds = duration_seconds(v.get("contentDetails", {}).get("duration", ""))
                if seconds < 180:
                    continue
                videos.append({
                    "video_id": v["id"], "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "tags": snippet.get("tags", []),
                    "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url"),
                    "duration": v.get("contentDetails", {}).get("duration", ""),
                    "views": int(v.get("statistics", {}).get("viewCount", 0)),
                    "published_at": snippet.get("publishedAt"),
                })
        token = page.get("nextPageToken")
        if not token:
            break
    report = {
        "long_video_count": len(videos),
        "matches": [v for v in videos if "yol" in v["title"].casefold() and ("cennet" in v["title"].casefold() or "saklı" in v["title"].casefold())],
        "audit": audit_videos(videos),
        "videos": videos,
        "read_only": True,
    }
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "full_long_video_audit.json"
    tmp = root / "full_long_video_audit.json.tmp"
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return {"long_video_count": len(videos), "matches": len(report["matches"]), "matched_videos": [{"video_id": v["video_id"], "title": v["title"], "views": v["views"]} for v in report["matches"]], "path": str(target)}
