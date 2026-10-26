"""البحث في Pixabay (صور وفيديو مجانية). المفتاح من https://pixabay.com/api/docs/ بعد تسجيل الدخول."""

from __future__ import annotations

import httpx

from .stock import StockError

API = "https://pixabay.com/api/"


def search(query: str, kind: str, api_key: str, aspect: str = "9:16", per_page: int = 8) -> list[dict]:
    """kind: "image" أو "video". بيرجع قايمة بدائل بنفس شكل Pexels."""
    if not api_key:
        raise StockError("مفيش مفتاح Pixabay. حطه من شاشة الإعدادات.")
    query = " ".join(query.split())[:100]  # Pixabay مابيقبلش أكتر من 100 حرف
    if not query:
        return []
    params = {"key": api_key, "q": query, "per_page": max(3, min(per_page, 200)), "safesearch": "true"}
    if kind == "video":
        url = API + "videos/"
    else:
        url = API
        params.update(image_type="photo", orientation="vertical" if aspect == "9:16" else "horizontal")
    try:
        response = httpx.get(url, params=params, timeout=20)
    except httpx.HTTPError as exc:
        raise StockError(f"مش قادر أوصل لـ Pixabay: {exc}") from exc
    if response.status_code in (400, 401, 403) and "key" in response.text.lower():
        raise StockError("مفتاح Pixabay غلط.")
    if response.status_code == 429:
        raise StockError("Pixabay بيقول طلبات كتير. استنى دقيقة وجرّب تاني.")
    if response.status_code >= 400:
        raise StockError(f"Pixabay رجّع خطأ {response.status_code}")
    hits = response.json().get("hits", [])
    if kind == "video":
        candidates = [c for c in (_video_candidate(h) for h in hits) if c]
        portrait = aspect == "9:16"
        # اللقطات اللي على نفس اتجاه الفيديو الأول
        candidates.sort(key=lambda c: ((c["height"] or 0) > (c["width"] or 0)) != portrait)
        return candidates
    return [_photo_candidate(h) for h in hits if h.get("largeImageURL")]


def _photo_candidate(hit: dict) -> dict:
    return {
        "source": "pixabay", "kind": "image", "id": str(hit["id"]),
        "thumb": hit.get("webformatURL") or hit.get("previewURL"),
        "url": hit["largeImageURL"],
        "width": hit.get("imageWidth"), "height": hit.get("imageHeight"),
        "author": hit.get("user"), "page": hit.get("pageURL"),
    }


def _video_candidate(hit: dict) -> dict | None:
    renditions = [v for v in (hit.get("videos") or {}).values() if v.get("url")]
    if not renditions:
        return None

    def score(v: dict) -> float:
        return abs(max(v.get("width") or 0, v.get("height") or 0) - 1920)

    best = min(renditions, key=score)
    thumb = next((v.get("thumbnail") for v in renditions if v.get("thumbnail")), None)
    if not thumb and hit.get("picture_id"):
        thumb = f"https://i.vimeocdn.com/video/{hit['picture_id']}_295x166.jpg"
    return {
        "source": "pixabay", "kind": "video", "id": str(hit["id"]),
        "thumb": thumb, "url": best["url"],
        "width": best.get("width"), "height": best.get("height"),
        "duration": hit.get("duration"),
        "author": hit.get("user"), "page": hit.get("pageURL"),
    }
