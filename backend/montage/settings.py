"""الإعدادات والمفاتيح. بتتحفظ في settings.local.json جنب المشروع (ومش بتترفع على GitHub)."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = Path(os.environ.get("MONTAGE_SETTINGS", ROOT / "settings.local.json"))

DEFAULTS: dict = {
    "pexels_api_key": "",
    "anthropic_api_key": "",
    "projects_dir": str(ROOT / "projects"),
    # large-v3 أدق موديل في العربي. على كارت شاشة قوي بيخلص دقيقة الصوت في ثواني.
    "whisper_model": "large-v3",
    "whisper_device": "auto",  # auto | cuda | cpu
    "default_aspect": "9:16",
}

SECRET_KEYS = ("pexels_api_key", "anthropic_api_key")
_lock = threading.Lock()


def load() -> dict:
    data = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        try:
            data.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
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
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
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
