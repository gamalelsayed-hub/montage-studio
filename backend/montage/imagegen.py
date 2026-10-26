"""توليد صور بالذكاء الاصطناعي (OpenAI Images) للقطات اللي مالهاش لقطة مناسبة في Pixabay.

المفتاح من شاشة الإعدادات. قواعد المحتوى (الستات محجبات ولبس شرعي) بتتبعت مع كل طلب.
"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

import httpx

from .content_rules import PROMPT_RULE

API = "https://api.openai.com/v1/images/generations"
FALLBACK_MODEL = "gpt-image-1"
SIZES = {"9:16": "1024x1536", "16:9": "1536x1024"}


class ImageGenError(RuntimeError):
    pass


def build_prompt(description: str) -> str:
    return (
        "A realistic, documentary-style photo for an Egyptian educational video about money and "
        "Islamic finance. Natural light, everyday Egyptian setting and people.\n"
        f"Scene (written in Egyptian Arabic): {description}\n"
        f"{PROMPT_RULE}\n"
        "No text, letters, numbers, logos or watermarks in the image."
    )


def _error_message(response: httpx.Response) -> str:
    try:
        error = response.json().get("error") or {}
    except ValueError:
        error = {}
    code = error.get("code") or ""
    if response.status_code == 401:
        return "مفتاح OpenAI غلط. راجعه في الإعدادات."
    if code == "moderation_blocked" or "safety" in (error.get("message") or "").lower():
        return "OpenAI رفض الوصف ده. جرّب تكتبه بشكل تاني."
    if code == "insufficient_quota" or response.status_code == 402:
        return "رصيد OpenAI خلص. اشحن من platform.openai.com ← Billing."
    if response.status_code == 429:
        return "OpenAI بيقول طلبات كتير. استنى دقيقة وجرّب تاني."
    if response.status_code == 403 and "verif" in (error.get("message") or "").lower():
        return "OpenAI محتاج توثيق الحساب الأول: platform.openai.com ← Settings ← Organization ← Verify."
    return f"OpenAI رجّع خطأ {response.status_code}: {(error.get('message') or '')[:200]}"


def _model_missing(response: httpx.Response) -> bool:
    if response.status_code not in (400, 404):
        return False
    try:
        error = response.json().get("error") or {}
    except ValueError:
        return False
    return error.get("code") == "model_not_found" or "model" in (error.get("param") or "")


def generate(description: str, aspect: str, config: dict, media_dir: Path) -> dict:
    """بيولّد صورة ويحفظها في media/ ويرجع بيانات الملف بنفس شكل اللقطات."""
    api_key = config.get("openai_api_key") or ""
    if not api_key:
        raise ImageGenError("مفيش مفتاح OpenAI. حطه من ⚙️ الإعدادات عشان تولّد صور.")
    model = config.get("openai_image_model") or FALLBACK_MODEL
    payload = {"model": model, "prompt": build_prompt(description), "size": SIZES.get(aspect, SIZES["9:16"]),
               "quality": "medium", "n": 1}
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = httpx.post(API, json=payload, headers=headers, timeout=180)
        if _model_missing(response) and model != FALLBACK_MODEL:
            payload["model"] = FALLBACK_MODEL
            response = httpx.post(API, json=payload, headers=headers, timeout=180)
    except httpx.HTTPError as exc:
        raise ImageGenError(f"مش قادر أوصل لـ OpenAI: {exc}") from exc
    if response.status_code >= 400:
        raise ImageGenError(_error_message(response))
    data = (response.json().get("data") or [{}])[0]
    if data.get("b64_json"):
        content = base64.b64decode(data["b64_json"])
    elif data.get("url"):
        content = httpx.get(data["url"], timeout=120).content
    else:
        raise ImageGenError("OpenAI مارجّعش صورة.")
    media_dir.mkdir(parents=True, exist_ok=True)
    name = f"ai_{uuid.uuid4().hex[:10]}.png"
    (media_dir / name).write_bytes(content)
    return {"file": name, "kind": "image", "source": "ai", "id": name, "thumb": None,
            "author": payload["model"], "page": None}
