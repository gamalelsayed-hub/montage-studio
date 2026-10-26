"""مطابقة التفريغ (كلمات بتوقيتها) مع فقرات السكريبت.

الفكرة: نحوّل السكريبت والتفريغ لسلسلتين كلمات بعد التطبيع، ونطابقهم بالترتيب
(SequenceMatcher). كل فقرة تاخد وقت أول وآخر كلمة اتطابقت منها. الفقرات اللي
ماتقالتش أو ماتطابقتش يتقدّر وقتها من اللي قبلها واللي بعدها.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

from .arabic import tokens

_PREFIXES = ("وال", "بال", "فال", "كال", "لل", "ال")


def _key(word: str) -> str:
    """مفتاح أخشن للكلمة عشان اختلافات الكتابة البسيطة بين السكريبت والتفريغ."""
    for prefix in _PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 2:
            word = word[len(prefix):]
            break
    else:
        if word[:1] in ("و", "ف", "ب") and len(word) >= 4:
            word = word[1:]
    if len(word) > 3 and word.endswith("ه"):
        word = word[:-1]
    return word


@dataclass
class ParagraphTiming:
    paragraph_id: str
    start: float
    end: float
    matched: int
    total: int
    estimated: bool  # True لو الوقت متقدّر مش متطابق

    @property
    def ratio(self) -> float:
        return self.matched / self.total if self.total else 0.0


def align(paragraphs: list[dict], words: list[dict], duration: float | None = None,
          min_ratio: float = 0.25) -> list[ParagraphTiming]:
    """paragraphs: [{id, text}] ، words: [{word, start, end}] من التفريغ."""
    script_keys: list[str] = []
    owner: list[int] = []
    totals: list[int] = []
    for index, para in enumerate(paragraphs):
        para_tokens = tokens(para["text"])
        totals.append(len(para_tokens))
        for tok in para_tokens:
            script_keys.append(_key(tok))
            owner.append(index)

    spoken_keys: list[str] = []
    spoken_index: list[int] = []
    for w_index, word in enumerate(words):
        for tok in tokens(word["word"]):
            spoken_keys.append(_key(tok))
            spoken_index.append(w_index)

    first: list[int | None] = [None] * len(paragraphs)
    last: list[int | None] = [None] * len(paragraphs)
    matched = [0] * len(paragraphs)
    matcher = SequenceMatcher(None, script_keys, spoken_keys, autojunk=False)
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            p = owner[block.a + k]
            w = spoken_index[block.b + k]
            matched[p] += 1
            if first[p] is None or w < first[p]:
                first[p] = w
            if last[p] is None or w > last[p]:
                last[p] = w

    timings: list[ParagraphTiming] = []
    for index, para in enumerate(paragraphs):
        total = totals[index]
        good = total > 0 and first[index] is not None and (
            matched[index] / total >= min_ratio or matched[index] >= 4)
        if good:
            start = float(words[first[index]]["start"])
            end = float(words[last[index]]["end"])
            timings.append(ParagraphTiming(para["id"], start, end, matched[index], total, False))
        else:
            timings.append(ParagraphTiming(para["id"], -1.0, -1.0, matched[index], total, True))

    _fill_estimates(timings, duration or (float(words[-1]["end"]) if words else 0.0))
    return timings


def _fill_estimates(timings: list[ParagraphTiming], duration: float) -> None:
    """يقدّر وقت الفقرات اللي ماتطابقتش، ويضمن إن الأوقات ماشية لقدام."""
    last_end = 0.0
    for t in timings:  # أي فقرة متطابقة بترجع لورا تتعامل كأنها ماتطابقتش
        if not t.estimated:
            if t.start + 0.01 < last_end - 2.0:
                t.estimated, t.start, t.end = True, -1.0, -1.0
            else:
                last_end = max(last_end, t.end)

    i = 0
    n = len(timings)
    while i < n:
        if not timings[i].estimated:
            i += 1
            continue
        j = i
        while j < n and timings[j].estimated:
            j += 1
        left = timings[i - 1].end if i > 0 else 0.0
        right = timings[j].start if j < n else duration
        if right < left:
            right = left
        weights = [max(t.total, 1) for t in timings[i:j]]
        total_weight = sum(weights)
        cursor = left
        for t, weight in zip(timings[i:j], weights):
            span = (right - left) * weight / total_weight
            t.start, t.end = cursor, cursor + span
            cursor += span
        i = j


def to_dicts(timings: list[ParagraphTiming]) -> list[dict]:
    return [{**asdict(t), "ratio": round(t.ratio, 3)} for t in timings]
