"""الإعدادات والمفاتيح. بتتحفظ في settings.local.json جنب المشروع (ومش بتترفع على GitHub)."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = Path(os.environ.get("MONTAGE_SETTINGS", ROOT / "settings.local.json"))

DEFAULTS: dict = {
    "pixabay_api_key": "",
    "pexels_api_key": "",
    "anthropic_api_key": "",
    "projects_dir": str(ROOT / "projects"),
    # large-v3 أدق موديل في العربي. على كارت شاشة قوي بيخلص دقيقة الصوت في ثواني.
    "whisper_model": "large-v3",
    "whisper_device": "auto",  # auto | cuda | cpu
    "default_aspect": "9:16",
    # توليد الصور بالذكاء الاصطناعي (النسخة التالتة)
    "openai_api_key": "",
    "openai_image_model": "gpt-image-1",
    # قالب الهوية: بيتطبق على الترجمة والعنوان واللوجو في كل الفيديوهات
    "brand": {
        "primary_color": "#13202E",
        "accent_color": "#1E6B47",
        "text_color": "#FFFFFF",
        "font": "Tajawal",
        "logo_position": "top-right",  # top-right | top-left | bottom-right | bottom-left
        "logo_size": 0.16,             # نسبة من عرض الفيديو
        "logo_opacity": 0.9,
    },
}

SECRET_KEYS = ("pixabay_api_key", "pexels_api_key", "anthropic_api_key", "openai_api_key")
BRAND_DIR = ROOT / "brand"  # اللوجو بيتحفظ هنا (ومش بيترفع على GitHub)
_lock = threading.Lock()


def load() -> dict:
    data = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        try:
            data.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    data["brand"] = {**DEFAULTS["brand"], **(data.get("brand") or {})}
    if not Path(data["projects_dir"]).parent.exists():
        # الفولدر اتنقل لمكان تاني: نرجع لفولدر projects جنب البرنامج
        data["projects_dir"] = DEFAULTS["projects_dir"]
    return data


def save(changes: dict) -> dict:
    with _lock:
        data = load()
        for key, value in changes.items():
            if key not in DEFAULTS:
                continue
            if key in SECRET_KEYS and isinstance(value, str) and value.startswith("••"):
                continue  # القيمة المخفية رجعت من الواجهة زي ما هي
            data[key] = value
        # بنحفظ اللي اتغيّر عن الافتراضي بس، عشان لو الفولدر اتنقل مايفضلش شايل مسار قديم
        stored = {k: v for k, v in data.items() if v != DEFAULTS.get(k)}
        SETTINGS_FILE.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
        return data


def public(data: dict | None = None) -> dict:
    """نسخة للواجهة: المفاتيح متخبية ماعدا آخر 4 حروف."""
    data = dict(data or load())
    for key in SECRET_KEYS:
        value = data.get(key) or ""
        data[key] = ("••••" + value[-4:]) if value else ""
        data[f"has_{key}"] = bool(value)
    return data


def projects_dir() -> Path:
    path = Path(load()["projects_dir"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def brand_logo() -> Path | None:
    logos = sorted(BRAND_DIR.glob("logo.*")) if BRAND_DIR.exists() else []
    return logos[0] if logos else None
