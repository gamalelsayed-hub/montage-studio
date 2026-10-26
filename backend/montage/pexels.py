"""البحث في Pexels (صور وفيديو مجانية)."""

from __future__ import annotations

import httpx

from .content_rules import is_allowed
from .stock import StockError

API = "https://api.pexels.com"


def _orientation(aspect: str) -> str:
    return "portrait" if aspect == "9:16" else "landscape"


def search(query: str, kind: str, api_key: str, aspect: str = "9:16", per_page: int = 8) -> list[dict]:
    """kind: "image" أو "video". بيرجع قايمة بدائل بشكل موحّد."""
    if not api_key:
        raise StockError("مفيش مفتاح Pexels. حطه من شاشة الإعدادات.")
    if not query.strip():
        return []
    path = "/videos/search" if kind == "video" else "/v1/search"
    params = {"query": query, "per_page": per_page, "orientation": _orientation(aspect)}
    try:
        response = httpx.get(API + path, params=params, headers={"Authorization": api_key}, timeout=20)
    except httpx.HTTPError as exc:
        raise StockError(f"مش قادر أوصل لـ Pexels: {exc}") from exc
    if response.status_code == 401:
        raise StockError("مفتاح Pexels غلط.")
    if response.status_code >= 400:
        raise StockError(f"Pexels رجّع خطأ {response.status_code}")
    data = response.json()
    if kind == "video":
        return [_video_candidate(v, aspect) for v in data.get("videos", [])
                if v.get("video_files") and is_allowed(v.get("url"))]
    return [_photo_candidate(p) for p in data.get("photos", []) if is_allowed(p.get("alt"))]


def _photo_candidate(photo: dict) -> dict:
    src = photo.get("src", {})
    return {
        "source": "pexels", "kind": "image", "id": str(photo["id"]),
        "thumb": src.get("medium") or src.get("small"),
        "url": src.get("large2x") or src.get("original"),
        "width": photo.get("width"), "height": photo.get("height"),
        "author": photo.get("photographer"), "page": photo.get("url"),
    }


def _video_candidate(video: dict, aspect: str) -> dict:
    target = 1920
    files = [f for f in video["video_files"] if f.get("file_type") == "video/mp4" and f.get("link")]
    files = files or video["video_files"]

    def score(f: dict) -> float:
        long_side = max(f.get("width") or 0, f.get("height") or 0)
        return abs(long_side - target)

    best = min(files, key=score)
    return {
        "source": "pexels", "kind": "video", "id": str(video["id"]),
        "thumb": video.get("image"), "url": best["link"],
        "width": best.get("width"), "height": best.get("height"),
        "duration": video.get("duration"),
        "author": (video.get("user") or {}).get("name"), "page": video.get("url"),
    }
