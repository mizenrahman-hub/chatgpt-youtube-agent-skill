"""Build YouTube API clients from Railway environment variables.

Secrets are read only from the environment and are never logged or written to
disk. This module performs no YouTube write operation by itself.
"""
from __future__ import annotations

import os
from typing import Mapping

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
REQUIRED_VARIABLES = (
    "YOUTUBE_CLIENT_ID",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_REFRESH_TOKEN",
)


class OAuthConfigurationError(RuntimeError):
    """Raised when the OAuth environment is missing or incomplete."""


def _oauth_values(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if environment is None else environment
    values = {name: source.get(name, "").strip() for name in REQUIRED_VARIABLES}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise OAuthConfigurationError(
            "Missing required OAuth variables: " + ", ".join(missing)
        )
    return values


def _credentials(
    environment: Mapping[str, str] | None,
    scopes: list[str],
) -> Credentials:
    values = _oauth_values(environment)
    credentials = Credentials(
        token=None,
        refresh_token=values["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=values["YOUTUBE_CLIENT_ID"],
        client_secret=values["YOUTUBE_CLIENT_SECRET"],
        scopes=scopes,
    )
    credentials.refresh(Request())
    return credentials


def build_youtube_client(environment: Mapping[str, str] | None = None):
    """Create an authenticated YouTube Data API client without mutating data."""
    credentials = _credentials(environment, [YOUTUBE_SCOPE])
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def build_youtube_analytics_client(environment: Mapping[str, str] | None = None):
    """Create a read-only YouTube Analytics API client."""
    credentials = _credentials(environment, [YOUTUBE_ANALYTICS_SCOPE])
    return build("youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False)


def verify_channel_access(youtube) -> None:
    """Run one read-only request and require exactly one authorized channel."""
    response = youtube.channels().list(part="id", mine=True).execute()
    if len(response.get("items", [])) != 1:
        raise OAuthConfigurationError("Expected exactly one authorized YouTube channel")
