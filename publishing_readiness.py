"""Preflight checks for the requested Türkiye publishing workflow.

This module does not publish or modify account settings.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Istanbul")
SLOTS = {"community": "15:30", "shorts_early": "16:30", "shorts_evening": "19:00"}
REQUIRED = {
    "youtube": ("YOUTUBE_WRITE_ENABLED", "YOUTUBE_REFRESH_TOKEN"),
    "shorts": ("SHORTS_ENABLED", "SHORTS_INBOX", "SHORTS_OUTPUT"),
}

def report():
    now = datetime.now(TZ)
    checks = {}
    for name, variables in REQUIRED.items():
        missing = [v for v in variables if not os.getenv(v)]
        checks[name] = {"ready": not missing, "missing": missing}
    write_enabled = os.getenv("YOUTUBE_WRITE_ENABLED", "").lower() in ("true", "1", "yes", "on")
    checks["youtube"]["ready"] = checks["youtube"]["ready"] and write_enabled
    if not write_enabled:
        checks["youtube"]["reason"] = "YouTube write access disabled; do not claim publication."
    checks["multiplatform"] = {"ready": False, "reason": "No verified Instagram/TikTok/Facebook publishing integration in this worker."}
    return {"checked_at": now.isoformat(), "timezone": "Europe/Istanbul", "requested_slots": SLOTS, "checks": checks}

if __name__ == "__main__":
    import json
    print(json.dumps(report(), ensure_ascii=False, indent=2))
