"""Safe, read-only comment review and contextual reply drafts.

No comments are posted. Drafts require separate explicit publish implementation.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

def _classify(text):
    lower = text.casefold()
    if re.search(r"https?://|www\\.|t\\.me/|wa\\.me/|telegram|whatsapp.*(?:yaz|ulaş)|bedava.*(?:para|ödül)", lower):
        return "spam"
    if any(term in lower for term in ("intihar", "kendimi öldür", "tehdit", "adresim", "telefon numaram")):
        return "review"
    if any(term in lower for term in ("sıkıcı", "berbat", "saçma", "kötü", "beğenmedim", "uzun olmuş", "ses kötü", "kalite kötü")):
        return "criticism"
    if "?" in lower or any(term in lower for term in ("nerede", "nasıl", "hangi", "kaç", "konum")):
        return "question"
    if any(term in lower for term in ("harika", "süper", "mükemmel", "eline sağlık", "teşekkür", "güzel")):
        return "praise"
    return "general"

def draft_reply(text, comment_id):
    category = _classify(text)
    if category in ("spam", "review"):
        return {"category": category, "reply": None, "requires_review": True}
    variants = {
        "criticism": [
            "Görüşünü paylaştığın için teşekkür ederim. Eleştirini dikkate alacağım; sonraki videoları daha iyi yapmak istiyorum.",
            "Geri bildirimin için teşekkürler. Herkese hitap etmeyebilir; geliştirmem gereken noktaları not alıyorum.",
        ],
        "question": [
            "Merak ettiğin için teşekkür ederim. Yanlış bilgi vermemek için bu soruyu kontrol edip netleştirmem gerekiyor.",
            "Güzel soru, teşekkürler. Emin olmadığım bir konuda yanlış yönlendirmek istemem; doğrulayıp paylaşacağım.",
        ],
        "praise": [
            "Çok teşekkür ederim, beğenmene sevindim! Yeni keşiflerde görüşmek üzere.",
            "Güzel yorumun için teşekkürler! Desteğin yeni rotalar için motive ediyor.",
        ],
        "general": [
            "Yorumun için teşekkür ederim, görüşünü paylaştığın için sevindim.",
            "Vakit ayırıp yorum yazdığın için teşekkürler!",
        ],
    }
    index = int(hashlib.sha256(comment_id.encode("utf-8")).hexdigest(), 16) % len(variants[category])
    return {"category": category, "reply": variants[category][index], "requires_review": category == "question"}

def collect_drafts(youtube, channel_id, output_dir, *, max_results=30):
    """Read top-level comments on owned channel's recent uploads; never post."""
    if not 1 <= max_results <= 100:
        raise ValueError("max_results out of range")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "reply_drafts.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    seen = {item["comment_id"] for item in previous.get("items", [])}
    items = list(previous.get("items", []))
    response = youtube.commentThreads().list(part="snippet", allThreadsRelatedToChannelId=channel_id, maxResults=max_results, order="time", textFormat="plainText").execute()
    for thread in response.get("items", []):
        top = thread.get("snippet", {}).get("topLevelComment", {})
        snippet = top.get("snippet", {})
        comment_id = top.get("id")
        if not comment_id or comment_id in seen:
            continue
        if snippet.get("authorChannelId", {}).get("value") == channel_id:
            continue
        # Skip already answered threads and avoid drafting duplicates.
        if int(thread.get("snippet", {}).get("totalReplyCount", 0)) > 0:
            continue
        text = snippet.get("textDisplay", "")
        result = draft_reply(text, comment_id)
        items.append({"comment_id": comment_id, "video_id": thread.get("snippet", {}).get("videoId"), "comment": text[:1000], **result, "status": "draft_only"})
        seen.add(comment_id)
    payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "publish_enabled": False, "items": items[-300:]}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return {"new_drafts": len(items) - len(previous.get("items", [])), "total_drafts": len(payload["items"])}
