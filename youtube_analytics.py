"""Read-only YouTube Analytics reporting helpers."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


def query_channel_analytics(
    analytics: Any,
    *,
    end_date: date | None = None,
    days: int = 28,
    max_results: int = 50,
) -> dict[str, Any]:
    if not 1 <= days <= 365:
        raise ValueError("days must be between 1 and 365")
    if not 1 <= max_results <= 200:
        raise ValueError("max_results must be between 1 and 200")

    end = end_date or (date.today() - timedelta(days=1))
    start = end - timedelta(days=days - 1)
    metrics = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage"

    channel = analytics.reports().query(
        ids="channel==MINE",
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        metrics=metrics,
    ).execute()

    videos = analytics.reports().query(
        ids="channel==MINE",
        startDate=start.isoformat(),
        endDate=end.isoformat(),
        metrics=metrics,
        dimensions="video",
        sort="-views",
        maxResults=max_results,
    ).execute()

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "channel": _rows(channel),
        "videos": _rows(videos),
    }


def _rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    headers = [header.get("name", "") for header in response.get("columnHeaders", [])]
    return [
        dict(zip(headers, row))
        for row in response.get("rows", [])
    ]
