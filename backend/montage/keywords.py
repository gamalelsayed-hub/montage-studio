"""تحويل أوصاف اللقطات (عربي) لكلمات بحث إنجليزي لمواقع اللقطات (Pixabay / Pexels).

لو فيه مفتاح Claude أو Gemini (مجاني) في الإعدادات: الذكاء الاصطناعي بيكتب كلمات البحث (أدق بكتير).
لو مافيش: قاموس صغير للكلمات الشايعة، والمستخدم يقدر يعدّل كلمة البحث من الواجهة.
"""

from __future__ import annotations

import json
import logging
import re

from .arabic import normalize
from .content_rules import PROMPT_RULE, apply_to_query

log = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-opus-5-5"
# موديلات Gemini المجانية (Free Tier)، بالترتيب: لو واحد اتشال أو مش متاح بنجرّب اللي بعده
GEMINI_MODELS = ("gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest")
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# القاموس الاحتياطي: الكلمة بعد التطبيع ← إنجليزي
_DICTIONARY = {
    "ايد": "hand", "ايدين": "hands", "قلم": "pen", "عقد": "contract", "تقسيط": "installment",
    "محل": "shop", "واجهه": "storefront", "سوق": "souk", "قديم": "old", "شوال": "sack",
    "قمح": "wheat", "توب": "fabric", "قماش": "fabric", "دنانير": "gold coins",
    "دهب": "gold", "ذهب": "gold", "فضه": "silver", "دراهم": "silver coins", "كف": "palm",
    "خزنه": "vault", "بنك": "bank", "سبايك": "gold bars", "سبيكه": "gold bar",
    "مطبعه": "printing press", "بنكنوت": "banknotes", "ورق": "paper", "غيط": "farm field",
    "مصنع": "factory", "نسيج": "textile", "عماره": "building", "بتتبني": "construction",
    "رغيف": "bread", "عيش": "bread", "جنيه": "egyptian pound", "جنيهات": "money",
    "رزمه": "cash stack", "فلوس": "money", "ورشه": "workshop", "خامات": "materials",
    "درج": "drawer", "بيتصافحوا": "handshake", "ترابيزه": "table", "شغل": "work",
    "بتمضي": "signing", "عمال": "workers", "بضاعه": "goods", "زباين": "customers",
    "فواتير": "bills", "ايصالات": "receipts", "كومه": "pile", "موبايل": "smartphone",
    "علبته": "box", "معرض": "showroom", "عربيات": "cars", "عربيه": "car", "ظرف": "envelope",
    "نتيجه": "calendar", "حيطه": "wall", "دايره": "circle", "واتساب": "whatsapp",
    "بيت": "house", "شقه": "apartment", "تلاجه": "refrigerator", "مسجد": "mosque",
    "قران": "quran", "مصحف": "quran", "كتاب": "book", "ست": "woman", "راجل": "man",
    "ناس": "people", "عيله": "family", "اطفال": "children", "طفل": "child",
    "شارع": "street", "القاهره": "cairo", "مصر": "egypt", "ساعه": "clock", "وقت": "time",
    "حساب": "calculator", "اله": "calculator", "كمبيوتر": "computer", "لابتوب": "laptop",
    "رز": "rice", "تمر": "dates", "جمل": "camel", "تاجر": "merchant", "بياع": "seller",
    "ميزان": "scale", "قرض": "loan", "دين": "debt", "ديون": "debt", "فايده": "interest rate",
    "فوايد": "interest rate", "مرتب": "salary", "شيك": "check", "كريدت": "credit card",
    "فيزا": "credit card", "كارت": "card", "قسط": "installment", "اقساط": "installments",
    "سياره": "car", "دكان": "shop", "صراف": "atm", "مكتب": "office", "موظف": "employee",
    "فلاح": "farmer", "زرع": "crops", "نخل": "palm trees", "صحرا": "desert", "مركب": "boat",
}

# الصفات بتيجي بعد الاسم في العربي، وبنحطها في الآخر عشان أول كلمة تبقى الحاجة الأساسية
_ADJECTIVES = {"old", "new"}
_ADJECTIVE_WORDS = {"قديم": "old", "قديمه": "old", "جديد": "new", "جديده": "new"}


def _translate(text: str) -> list[str]:
    words: list[str] = []
    for token in normalize(text).split():
        for candidate in (token, token[2:] if token.startswith("ال") else token,
                          token[1:] if token[:1] in "وبف" else token):
            english = _DICTIONARY.get(candidate) or _ADJECTIVE_WORDS.get(candidate)
            if english:
                if english not in words:
                    words.append(english)
                break
    return words


def _fallback_query(description: str) -> str:
    """الوصف غالبًا «المكان: التفاصيل». المكان هو الأهم، وبعده حاجة واحدة من التفاصيل.

    الكلمات الأقل بتجيب نتايج أدق، والبحث بيقلّل الكلمات لوحده لو مالقاش (stock.broader_queries).
    """
    head, sep, tail = description.partition(":")
    if not sep:
        head, tail = re.split(r"[،,]", description, maxsplit=1)[0], description
    main = _translate(head)
    details = [w for w in _translate(tail) if w not in main and w not in _ADJECTIVES]
    nouns = [w for w in main if w not in _ADJECTIVES] + details
    adjectives = [w for w in main if w in _ADJECTIVES]
    words = " ".join(nouns[:2] + adjectives[:1]).split()
    return " ".join(dict.fromkeys(words))  # "gold coins" + "gold" ← "gold coins"


def _prompt(descriptions: list[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {d}" for i, d in enumerate(descriptions))
    return (
        "These are Arabic (Egyptian) descriptions of b-roll shots for a video. For each one, "
        "write a short English stock-footage search query (2-5 words) that will find a good "
        "match on free stock sites (Pixabay, Pexels). Prefer concrete, visual nouns. If a description offers alternatives "
        "('or' / 'أو'), pick the easier one to find.\n"
        f"{PROMPT_RULE}\n\n"
        'Answer with JSON only: {"queries": ["...", "..."]} in the same order.\n\n'
        f"{numbered}"
    )


def _parse(text: str, count: int) -> list[str]:
    match = re.search(r"\{.*\}", text, re.S)
    queries = json.loads(match.group(0) if match else text)["queries"]
    if len(queries) != count:
        raise ValueError("عدد كلمات البحث مش زي عدد اللقطات")
    return [str(q) for q in queries]


def _claude_queries(descriptions: list[str], api_key: str) -> list[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": _prompt(descriptions)}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude refused the request")
    text = "".join(block.text for block in response.content if block.type == "text")
    return _parse(text, len(descriptions))


def _gemini_queries(descriptions: list[str], api_key: str) -> list[str]:
    import httpx

    body = {"contents": [{"parts": [{"text": _prompt(descriptions)}]}],
            "generationConfig": {"responseMimeType": "application/json"}}
    for model in GEMINI_MODELS:
        response = httpx.post(GEMINI_API.format(model=model), json=body, timeout=60,
                              headers={"x-goog-api-key": api_key})
        if response.status_code == 404:  # الموديل اتشال: نجرّب اللي بعده
            continue
        response.raise_for_status()
        parts = (response.json().get("candidates") or [{}])[0].get("content", {}).get("parts") or []
        return _parse("".join(part.get("text", "") for part in parts), len(descriptions))
    raise RuntimeError("مفيش موديل Gemini متاح")


def make_queries(descriptions: list[str], anthropic_api_key: str = "",
                 gemini_api_key: str = "") -> tuple[list[str], str]:
    """بيرجع (كلمات البحث، المصدر: "claude" أو "gemini" أو "dictionary")."""
    source = "dictionary"
    queries: list[str] | None = None
    for name, key, ask in (("claude", anthropic_api_key, _claude_queries), ("gemini", gemini_api_key, _gemini_queries)):
        if queries is not None or not key or not descriptions:
            continue
        try:
            queries = ask(descriptions, key)
            source = name
        except Exception as exc:  # الشبكة أو المفتاح: نجرّب اللي بعده، وآخر حاجة القاموس
            log.warning("%s keywords failed: %s", name, exc)
    if queries is None:
        queries = [_fallback_query(d) for d in descriptions]
    return [apply_to_query(q) for q in queries], source
