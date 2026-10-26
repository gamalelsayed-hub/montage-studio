"""تحويل أوصاف اللقطات (عربي) لكلمات بحث إنجليزي لمواقع اللقطات (Pixabay / Pexels).

لو فيه مفتاح Claude في الإعدادات: Claude بيكتب كلمات البحث (أدق بكتير).
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

# القاموس الاحتياطي: الكلمة بعد التطبيع ← إنجليزي
_DICTIONARY = {
    "ايد": "hand", "ايدين": "hands", "قلم": "pen", "عقد": "contract", "تقسيط": "installment",
    "محل": "shop", "واجهه": "storefront", "سوق": "market", "قديم": "old", "شوال": "sack",
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
}


def _fallback_query(description: str) -> str:
    words: list[str] = []
    for token in normalize(description).split():
        for candidate in (token, token[2:] if token.startswith("ال") else token,
                          token[1:] if token[:1] in "وبف" else token):
            english = _DICTIONARY.get(candidate)
            if english and english not in words:
                words.append(english)
                break
    return " ".join(words[:4])


def _claude_queries(descriptions: list[str], api_key: str) -> list[str]:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    numbered = "\n".join(f"{i + 1}. {d}" for i, d in enumerate(descriptions))
    prompt = (
        "These are Arabic (Egyptian) descriptions of b-roll shots for a video. For each one, "
        "write a short English stock-footage search query (2-5 words) that will find a good "
        "match on free stock sites (Pixabay, Pexels). Prefer concrete, visual nouns. If a description offers alternatives "
        "('or' / 'أو'), pick the easier one to find.\n"
        f"{PROMPT_RULE}\n\n"
        'Answer with JSON only: {"queries": ["...", "..."]} in the same order.\n\n'
        f"{numbered}"
    )
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude refused the request")
    text = "".join(block.text for block in response.content if block.type == "text")
    match = re.search(r"\{.*\}", text, re.S)
    queries = json.loads(match.group(0) if match else text)["queries"]
    if len(queries) != len(descriptions):
        raise ValueError("عدد كلمات البحث مش زي عدد اللقطات")
    return [str(q) for q in queries]


def make_queries(descriptions: list[str], anthropic_api_key: str = "") -> tuple[list[str], str]:
    """بيرجع (كلمات البحث، المصدر: "claude" أو "dictionary")."""
    source = "dictionary"
    queries: list[str] | None = None
    if anthropic_api_key and descriptions:
        try:
            queries = _claude_queries(descriptions, anthropic_api_key)
            source = "claude"
        except Exception as exc:  # الشبكة أو المفتاح: نكمل بالقاموس
            log.warning("Claude keywords failed, using dictionary: %s", exc)
    if queries is None:
        queries = [_fallback_query(d) for d in descriptions]
    return [apply_to_query(q) for q in queries], source
