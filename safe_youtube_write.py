"""Narrow, approval-gated YouTube metadata updates.

This module intentionally exposes no upload or delete operation.  A caller must
pin one video id, preview the exact changes, and supply the preview fingerprint
before any API request that mutates YouTube is made.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Iterable


class SafetyError(RuntimeError):
    """Raised when a write is not explicitly and narrowly authorized."""


def _clean_tags(tags: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        value = str(tag).strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


@dataclass(frozen=True)
class MetadataProposal:
    video_id: str
    title: str
    description: str
    tags: tuple[str, ...]
    category_id: str | None = None

    def canonical(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id.strip(),
            "title": self.title.strip(),
            "description": self.description.strip(),
            "tags": _clean_tags(self.tags),
            "category_id": self.category_id.strip() if self.category_id else None,
        }

    def approval_code(self) -> str:
        payload = json.dumps(
            self.canonical(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]


def preview(proposal: MetadataProposal) -> dict[str, Any]:
    """Return the exact proposed values plus the code required for execution."""
    data = proposal.canonical()
    data["approval_code"] = proposal.approval_code()
    data["writes_enabled"] = os.getenv("YOUTUBE_WRITE_ENABLED") == "true"
    return data


def apply_metadata_update(
    youtube: Any,
    proposal: MetadataProposal,
    *,
    approval_code: str,
    allowed_video_id: str | None = None,
) -> dict[str, Any]:
    """Update snippet metadata after all safety gates pass.

    The only mutating API call reachable here is ``videos.update``.  Existing
    snippet fields that are not part of the proposal are preserved.
    """
    if os.getenv("YOUTUBE_WRITE_ENABLED") != "true":
        raise SafetyError("Writes are disabled")

    allowed = (allowed_video_id or os.getenv("YOUTUBE_ALLOWED_VIDEO_ID", "")).strip()
    proposed = proposal.canonical()
    if not allowed or proposed["video_id"] != allowed:
        raise SafetyError("Video is not on the single-video allowlist")
    if approval_code != proposal.approval_code():
        raise SafetyError("Approval code does not match the exact preview")
    if not proposed["title"] or len(proposed["title"]) > 100:
        raise SafetyError("Title must contain 1-100 characters")
    if len(proposed["description"]) > 5000:
        raise SafetyError("Description exceeds 5000 characters")

    current = youtube.videos().list(
        part="snippet", id=proposed["video_id"]
    ).execute()
    items = current.get("items", [])
    if len(items) != 1:
        raise SafetyError("Expected exactly one matching video")

    old_snippet = dict(items[0].get("snippet", {}))
    new_snippet = dict(old_snippet)
    new_snippet.update(
        title=proposed["title"],
        description=proposed["description"],
        tags=proposed["tags"],
    )
    if proposed["category_id"]:
        new_snippet["categoryId"] = proposed["category_id"]

    result = youtube.videos().update(
        part="snippet",
        body={"id": proposed["video_id"], "snippet": new_snippet},
    ).execute()
    return {
        "video_id": proposed["video_id"],
        "backup": old_snippet,
        "updated": result,
        "approval_code": proposal.approval_code(),
    }
