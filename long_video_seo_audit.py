"""Read-only metadata audit for long-form travel and challenge videos.

Do not automatically rewrite published metadata. CTR and retention require
separate YouTube Studio validation before any title/thumbnail change.
"""
from __future__ import annotations
import re

def duration_seconds(iso):
    match = re.fullmatch(r"P(?:([0-9]+)D)?T?(?:([0-9]+)H)?(?:([0-9]+)M)?(?:([0-9]+)S)?", iso or "")
    if not match:
        return 0
    days, hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds

def content_era(title):
    text = (title or "").casefold()
    if any(term in text for term in ("mağara", "kamp", "kanyon", "şelale", "doğa", "24 saat", "48 saat", "gezi", "rota", "keşif", "motorla", "ormanda", "terk edilmiş", "antalya", "olympos")):
        return "gezi_kamp_challenge"
    return "diger_veya_eski_donem"

def audit_videos(videos, analytics_rows=None):
    by_id = {row.get("video"): row for row in (analytics_rows or [])}
    audit = []
    for video in videos:
        seconds = duration_seconds(video.get("duration", ""))
        if seconds < 180:
            continue  # shorts and brief clips are outside this audit
        title = video.get("title", "").strip()
        issues = []
        if len(title) > 70:
            issues.append("Baslik 70 karakterden uzun; mobilde kesilme riskini incele")
        if len(title) < 25:
            issues.append("Baslik kisa; konu ve merak unsuru net mi kontrol et")
        if title.count("!") >= 3 or title.isupper():
            issues.append("Abartili tipografi; guven ve tiklama uyumunu kontrol et")
        if not any(term in title.casefold() for term in ("mağara", "kamp", "kanyon", "şelale", "antalya", "24 saat", "48 saat", "gezi", "motor", "ormanda", "terk edilmiş")) and content_era(title) == "gezi_kamp_challenge":
            issues.append("Konuyu arama niyetiyle eslestir")
        row = by_id.get(video.get("video_id"), {})
        audit.append({
            "video_id": video.get("video_id"),
            "title": title,
            "duration_seconds": seconds,
            "content_group": content_era(title),
            "views_lifetime": video.get("views", 0),
            "views_last_28_days": row.get("views"),
            "average_view_duration": row.get("averageViewDuration"),
            "average_view_percentage": row.get("averageViewPercentage"),
            "issues": issues,
            "thumbnail_review": "3-4 kelimeyi gecmeyen kapak metni; net ana ozne, guclu duygu, mobil okunabilirlik; mevcut gorsel gorulmeden degisiklik yapma",
            "seo_review": "Konuyla uyumlu dogal aciklama, bolge/rota bilgisi, ilgili uzun videolar ve oynatma listesi baglantilari",
            "action": "manual_review_before_any_write",
            "ctr_available": False,
            "note": "CTR/gosterim bu raporda yok. Studio verisi olmadan performans artisi iddia etme.",
        })
    return audit
