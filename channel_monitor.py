"""Read-only YouTube channel monitoring helpers.

Only YouTube Data API list operations are used here. This module has no
publishing, update, upload, or delete capability.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def scan_channel(youtube: Any, *, max_results: int = 10) -> dict[str, Any]:
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be between 1 and 50")

    channels = youtube.channels().list(
        part="id,snippet,contentDetails,statistics", mine=True
    ).execute()
    items = channels.get("items", [])
    if len(items) != 1:
        raise RuntimeError("Expected exactly one authorized YouTube channel")

    channel = items[0]
    uploads = channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads:
        raise RuntimeError("Authorized channel has no uploads playlist")

    playlist = youtube.playlistItems().list(
        part="contentDetails", playlistId=uploads, maxResults=max_results
    ).execute()
    video_ids = [
        item.get("contentDetails", {}).get("videoId", "")
        for item in playlist.get("items", [])
    ]
    video_ids = [video_id for video_id in video_ids if video_id]

    videos: list[dict[str, Any]] = []
    if video_ids:
        response = youtube.videos().list(
            part="id,snippet,contentDetails,statistics", id=",".join(video_ids)
        ).execute()
        for video in response.get("items", []):
            snippet = video.get("snippet", {})
            statistics = video.get("statistics", {})
            videos.append({
                "video_id": video.get("id"),
                "title": snippet.get("title", ""),
                "published_at": snippet.get("publishedAt"),
                "duration": video.get("contentDetails", {}).get("duration"),
                "views": int(statistics.get("viewCount", 0)),
                "likes": int(statistics.get("likeCount", 0)),
                "comments": int(statistics.get("commentCount", 0)),
            })

    stats = channel.get("statistics", {})
    return {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "channel_id": channel.get("id"),
        "channel_title": channel.get("snippet", {}).get("title", ""),
        "subscribers": int(stats.get("subscriberCount", 0)),
        "channel_views": int(stats.get("viewCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
        "recent_videos": videos,
    }
