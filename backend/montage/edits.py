"""القص التلقائي من التفريغ: السكتات الطويلة واللغبطة (لما يعيد نفس الجملة).

كل قص بيتعلّم بـ "auto" عشان يقدر يرجّعه كله بضغطة، أو يرجّع واحد بس من التايم لاين.
مافيش حاجة بتتمسح من التسجيل نفسه: القص بيتطبق وقت التصدير بس.
"""

from __future__ import annotations

from .arabic import tokens

SILENCE_MIN = 0.8   # أي سكتة أطول من كده تتقص
KEEP_PAD = 0.2      # نسيب نفس قبل وبعد الكلام عشان القص مايبقاش ناشف
RETAKE_MIN_WORDS = 2
RETAKE_MAX_WORDS = 8
RETAKE_MAX_GAP = 4.0  # الإعادة لازم تبقى قريبة من المحاولة الأولى


def silence_cuts(words: list[dict], duration: float, min_gap: float = SILENCE_MIN,
                 pad: float = KEEP_PAD) -> list[dict]:
    """السكتات بين الكلمات (وفي أول وآخر التسجيل)."""
    cuts: list[dict] = []
    if not words:
        return cuts
    edges = [(0.0, float(words[0]["start"]))]
    edges += [(float(a["end"]), float(b["start"])) for a, b in zip(words, words[1:])]
    edges.append((float(words[-1]["end"]), duration))
    for gap_start, gap_end in edges:
        start = gap_start + pad if gap_start > 0 else 0.0
        end = gap_end - pad if gap_end < duration else duration
        if gap_end - gap_start >= min_gap and end - start >= 0.3:
            cuts.append({"start": round(start, 3), "end": round(end, 3), "auto": "silence"})
    return cuts


def _keys(words: list[dict]) -> list[str]:
    return [" ".join(tokens(w["word"])) for w in words]


def retake_cuts(words: list[dict], pad: float = KEEP_PAD) -> list[dict]:
    """لما يقول كام كلمة ويرجع يقولهم تاني من الأول: نقص المحاولة الأولى.

    مثال: «الفلوس دي جت … الفلوس دي جت منين» ← يتشال «الفلوس دي جت» الأولانية.
    """
    keys = _keys(words)
    cuts: list[dict] = []
    i = 0
    while i < len(words):
        found = 0
        for n in range(min(RETAKE_MAX_WORDS, (len(words) - i) // 2), RETAKE_MIN_WORDS - 1, -1):
            first, second = keys[i:i + n], keys[i + n:i + 2 * n]
            if first == second and all(first):
                gap = float(words[i + n]["start"]) - float(words[i + n - 1]["end"])
                if gap <= RETAKE_MAX_GAP:
                    found = n
                    break
        if found:
            start = max(float(words[i]["start"]) - pad / 2, 0.0)
            end = float(words[i + found]["start"]) - pad / 2
            if end > start:
                cuts.append({"start": round(start, 3), "end": round(end, 3), "auto": "retake"})
            i += found
        else:
            i += 1
    return cuts


def auto_cuts(words: list[dict], duration: float, silence: bool = True, retakes: bool = True,
              min_gap: float = SILENCE_MIN) -> list[dict]:
    cuts = (silence_cuts(words, duration, min_gap) if silence else []) + (retake_cuts(words) if retakes else [])
    cuts.sort(key=lambda c: c["start"])
    for index, cut in enumerate(cuts, 1):
        cut["id"] = f"auto{index}"
    return cuts
