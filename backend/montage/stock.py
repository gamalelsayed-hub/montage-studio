"""مصادر اللقطات المجانية (Pixabay وPexels): البحث في المصدر اللي ليه مفتاح، والتنزيل."""

from __future__ import annotations

from pathlib import Path

import httpx


class StockError(RuntimeError):
    pass


NO_KEY_MESSAGE = "مفيش مفتاح لقطات. حط مفتاح Pixabay المجاني من شاشة الإعدادات."


def providers(config: dict) -> list[tuple[str, str]]:
    """المصادر اللي ليها مفتاح بالترتيب: [(الاسم، المفتاح)]."""
    order = (("pixabay", "pixabay_api_key"), ("pexels", "pexels_api_key"))
    return [(name, config[key]) for name, key in order if config.get(key)]


def has_key(config: dict) -> bool:
    return bool(providers(config))


def search(query: str, kind: str, config: dict, aspect: str = "9:16", per_page: int = 8) -> list[dict]:
    """يدوّر في أول مصدر ليه مفتاح، ولو مالقاش نتايج يجرّب اللي بعده."""
    from . import pexels, pixabay

    available = providers(config)
    if not available:
        raise StockError(NO_KEY_MESSAGE)
    modules = {"pixabay": pixabay, "pexels": pexels}
    errors: list[str] = []
    for name, key in available:
        try:
            results = modules[name].search(query, kind, key, aspect, per_page)
        except StockError as exc:
            errors.append(str(exc))
            continue
        if results:
            return results
    if errors and len(errors) == len(available):
        raise StockError(" / ".join(errors))
    return []


def download(candidate: dict, media_dir: Path) -> str:
    """ينزّل اللقطة لفولدر المشروع ويرجع اسم الملف."""
    media_dir.mkdir(parents=True, exist_ok=True)
    ext = ".mp4" if candidate["kind"] == "video" else ".jpg"
    source = candidate.get("source") or "stock"
    name = f"{source}_{candidate['kind']}_{candidate['id']}{ext}"
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
        raise StockError(f"فشل تنزيل اللقطة: {exc}") from exc
    tmp.replace(target)
    return name
