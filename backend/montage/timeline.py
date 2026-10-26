"""بناء التايم لاين الأولي: كل لقطة في ثانيتها حسب الفقرة اللي مربوطة بيها.

شكل ملف timeline.json:
{
  "version": 2, "aspect": "9:16", "duration": 540.2,
  "base": {"file": "recording.mp4", "has_video": true, "volume": 1.0, "clean_audio": true},
  "cuts": [{"id": "cut1", "start": 12.0, "end": 13.5, "auto": "silence" | "retake" | null}],
  "clips": [{"id": "clip1", "shot_id": "shot1", "kind": "image", "start": 3.2, "end": 8.0,
             "description": "...", "query": "...", "motion": "zoom_in", "volume": 0.0,
             "fit": "cover" | "contain", "estimated": false, "page": null,
             "media": {...} | null, "candidates": [...]}],
  "markers": [{"paragraph_id": "p3", "start": 1.0, "end": 9.0, "estimated": false}],
  "captions": [{"id": "cap1", "start": 1.0, "end": 2.6, "text": "..."}],
  "caption_style": {"enabled": true, "font": "Tajawal", "size": 64, ...},
  "brand": {"logo": true, "title": true}
}
الأوقات كلها بتوقيت التسجيل الأصلي (قبل القص).
- estimated: اللقطة مربوطة بفقرة وقتها متقدّر (ماتلقتش في التسجيل) فلازم يراجعها بنفسه.
- page: لقطة صورة صفحة اللوحة رقم N في أول القسم بتاعها.
"""

from __future__ import annotations

from .captions import DEFAULT_STYLE

MIN_CLIP = 2.5
MAX_CLIP = 7.0
PAGE_CLIP = 4.0


def _clip(clip_id: str, kind: str, description: str, start: float, length: float, **extra) -> dict:
    clip = {
        "id": clip_id, "shot_id": None, "kind": kind, "description": description, "query": "",
        "start": round(start, 3), "end": round(start + length, 3),
        "motion": "zoom_in" if kind == "image" else "none", "volume": 0.0, "fit": "cover",
        "estimated": False, "page": None, "media": None, "candidates": [],
    }
    clip.update(extra)
    return clip


def page_clips(script: dict, timings: dict[str, dict], pages: dict[int, dict], duration: float) -> list[dict]:
    """صورة صفحة اللوحة في أول كل قسم «صفحة N» (لو صورتها مرفوعة)."""
    clips: list[dict] = []
    for section in script.get("sections", []):
        page = section.get("page")
        media = pages.get(page) if page is not None else None
        first = next((p for p in script["paragraphs"] if p["section_id"] == section["id"]), None)
        timing = timings.get(first["id"]) if first else None
        if not media or not timing or timing["start"] >= duration - 0.5:
            continue
        clips.append(_clip(f"page_{page}", "image", section["title"] or f"صفحة {page}", timing["start"],
                           PAGE_CLIP, motion="none", fit="contain", page=page,
                           estimated=bool(timing.get("estimated")), media=dict(media)))
    return clips


def build_clips(shots: list[dict], timings: dict[str, dict], duration: float,
                reserved: dict[str, float] | None = None) -> list[dict]:
    """reserved: فقرات أولها محجوز لصورة الصفحة ← اللقطات تبدأ بعدها بالثواني دي."""
    by_paragraph: dict[str | None, list[dict]] = {}
    for shot in shots:
        by_paragraph.setdefault(shot.get("paragraph_id"), []).append(shot)

    clips: list[dict] = []
    for paragraph_id, group in by_paragraph.items():
        timing = timings.get(paragraph_id) if paragraph_id else None
        if timing:
            p_start, p_end = timing["start"], max(timing["end"], timing["start"] + MIN_CLIP)
            if duration and (p_start >= duration - 0.5 or
                             (timing.get("estimated") and p_start > duration - MIN_CLIP)):
                continue  # الفقرة دي ماتقالتش في التسجيل (التسجيل أقصر من السكريبت)
            p_start += (reserved or {}).get(paragraph_id, 0.0)
            p_end = max(p_end, p_start + MIN_CLIP)
        else:
            p_start, p_end = 0.0, MIN_CLIP * len(group)
        slot = (p_end - p_start) / len(group)
        for index, shot in enumerate(group):
            start = p_start + slot * index
            length = min(max(slot, MIN_CLIP), MAX_CLIP)
            clips.append(_clip(f"clip_{shot['id']}", shot["kind"], shot["description"], start, length,
                               shot_id=shot["id"], estimated=bool(timing is None or timing.get("estimated"))))
    return clips


def fix_overlaps(clips: list[dict], duration: float) -> list[dict]:
    clips.sort(key=lambda c: (c["start"], 0 if c.get("page") else 1))
    # مافيش لقطتين فوق بعض: كل لقطة تخلص قبل اللي بعدها ما تبدأ
    for current, following in zip(clips, clips[1:]):
        if current["end"] > following["start"]:
            current["end"] = round(max(following["start"], current["start"] + 0.5), 3)
            if current["end"] > following["start"]:
                following["start"] = current["end"]
                following["end"] = max(following["end"], following["start"] + 0.5)
    if duration:
        for clip in clips:
            clip["start"] = min(clip["start"], max(duration - 0.5, 0))
            clip["end"] = min(clip["end"], duration)
    return clips


def build_timeline(script: dict, timings: list[dict], duration: float, base: dict,
                   aspect: str, pages: dict[int, dict] | None = None, captions: list[dict] | None = None,
                   cuts: list[dict] | None = None) -> dict:
    timing_map = {t["paragraph_id"]: t for t in timings}
    pages_list = page_clips(script, timing_map, pages or {}, duration)
    reserved: dict[str, float] = {}
    for section in script.get("sections", []):
        if any(c["page"] == section.get("page") for c in pages_list):
            first = next((p for p in script["paragraphs"] if p["section_id"] == section["id"]), None)
            if first:
                reserved[first["id"]] = PAGE_CLIP
    clips = fix_overlaps(pages_list + build_clips(script["shots"], timing_map, duration, reserved), duration)
    return normalize({
        "version": 2,
        "aspect": aspect,
        "duration": round(duration, 3),
        "base": {"clean_audio": True, **base},
        "cuts": cuts or [],
        "clips": clips,
        "markers": [{"paragraph_id": t["paragraph_id"], "start": round(t["start"], 3),
                     "end": round(min(t["end"], duration), 3), "estimated": t["estimated"]}
                    for t in timings if t["start"] < duration],
        "captions": captions or [],
    })


def normalize(timeline: dict) -> dict:
    """تايم لاين قديم (النسخة الأولى) ← يتكمّل بالقيم الافتراضية للحاجات الجديدة."""
    timeline.setdefault("cuts", [])
    timeline.setdefault("markers", [])
    timeline.setdefault("captions", [])
    timeline["caption_style"] = {**DEFAULT_STYLE, **(timeline.get("caption_style") or {})}
    timeline.pop("music", None)  # مافيش موسيقى خلفية (قرار صاحب المشروع)
    timeline.setdefault("brand", {"logo": True, "title": False})
    timeline["base"].setdefault("clean_audio", True)
    for clip in timeline.get("clips", []):
        clip.setdefault("fit", "cover")
        clip.setdefault("estimated", False)
        clip.setdefault("page", None)
    timeline["version"] = 2
    return timeline


def kept_duration(duration: float, cuts: list[dict]) -> float:
    removed = 0.0
    for start, end in merge_cuts(cuts, duration):
        removed += end - start
    return max(duration - removed, 0.0)


def merge_cuts(cuts: list[dict], duration: float | None = None) -> list[tuple[float, float]]:
    ranges = sorted((max(0.0, c["start"]), c["end"]) for c in cuts if c["end"] > c["start"])
    merged: list[tuple[float, float]] = []
    for start, end in ranges:
        if duration is not None:
            end = min(end, duration)
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
