"""البحث في Pexels وتنزيل اللقطة المختارة."""

from __future__ import annotations

from pathlib import Path

import httpx

API = "https://api.pexels.com"


class PexelsError(RuntimeError):
    pass


def _orientation(aspect: str) -> str:
    return "portrait" if aspect == "9:16" else "landscape"


def search(query: str, kind: str, api_key: str, aspect: str = "9:16", per_page: int = 8) -> list[dict]:
    """kind: "image" أو "video". بيرجع قايمة بدائل بشكل موحّد."""
    if not api_key:
        raise PexelsError("مفيش مفتاح Pexels. حطه من شاشة الإعدادات.")
    if not query.strip():
        return []
    path = "/videos/search" if kind == "video" else "/v1/search"
    params = {"query": query, "per_page": per_page, "orientation": _orientation(aspect)}
    try:
        response = httpx.get(API + path, params=params, headers={"Authorization": api_key}, timeout=20)
    except httpx.HTTPError as exc:
        raise PexelsError(f"مش قادر أوصل لـ Pexels: {exc}") from exc
    if response.status_code == 401:
        raise PexelsError("مفتاح Pexels غلط.")
    if response.status_code >= 400:
        raise PexelsError(f"Pexels رجّع خطأ {response.status_code}")
    data = response.json()
    if kind == "video":
        return [_video_candidate(v, aspect) for v in data.get("videos", []) if v.get("video_files")]
    return [_photo_candidate(p) for p in data.get("photos", [])]


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


def download(candidate: dict, media_dir: Path) -> str:
    """ينزّل اللقطة لفولدر المشروع ويرجع اسم الملف."""
    media_dir.mkdir(parents=True, exist_ok=True)
    ext = ".mp4" if candidate["kind"] == "video" else ".jpg"
    name = f"pexels_{candidate['kind']}_{candidate['id']}{ext}"
    target = media_dir / name
    if target.exists() and target.stat().st_size > 0:
        return name
    tmp = target.with_suffix(target.suffix + ".part")
    try:
        with httpx.stream("GET", candidate["url"], timeout=120, follow_redirects=True) as response:
            response.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes(1 << 16):
                    handle.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        raise PexelsError(f"فشل تنزيل اللقطة: {exc}") from exc
    tmp.replace(target)
    return name
