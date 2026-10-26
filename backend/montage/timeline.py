"""بناء التايم لاين الأولي: كل لقطة في ثانيتها حسب الفقرة اللي مربوطة بيها.

شكل ملف timeline.json:
{
  "version": 1, "aspect": "9:16", "duration": 540.2,
  "base": {"file": "recording.mp4", "has_video": true, "volume": 1.0},
  "cuts": [{"id": "cut1", "start": 12.0, "end": 13.5}],     # أجزاء متشالة من التسجيل
  "clips": [{"id": "clip1", "shot_id": "shot1", "kind": "image", "start": 3.2, "end": 8.0,
             "description": "...", "query": "...", "motion": "zoom_in", "volume": 0.0,
             "media": {...} | null, "candidates": [...]}],
  "markers": [{"paragraph_id": "p3", "start": 1.0, "end": 9.0, "estimated": false}]
}
الأوقات كلها بتوقيت التسجيل الأصلي (قبل القص).
"""

from __future__ import annotations

MIN_CLIP = 2.5
MAX_CLIP = 7.0


def build_clips(shots: list[dict], timings: dict[str, dict], duration: float) -> list[dict]:
    by_paragraph: dict[str | None, list[dict]] = {}
    for shot in shots:
        by_paragraph.setdefault(shot.get("paragraph_id"), []).append(shot)

    clips: list[dict] = []
    for paragraph_id, group in by_paragraph.items():
        timing = timings.get(paragraph_id) if paragraph_id else None
        if timing:
            p_start, p_end = timing["start"], max(timing["end"], timing["start"] + MIN_CLIP)
        else:
            p_start, p_end = 0.0, MIN_CLIP * len(group)
        slot = (p_end - p_start) / len(group)
        for index, shot in enumerate(group):
            start = p_start + slot * index
            length = min(max(slot, MIN_CLIP), MAX_CLIP)
            clips.append({
                "id": f"clip_{shot['id']}",
                "shot_id": shot["id"],
                "kind": shot["kind"],
                "description": shot["description"],
                "query": "",
                "start": round(start, 3),
                "end": round(start + length, 3),
                "motion": "zoom_in" if shot["kind"] == "image" else "none",
                "volume": 0.0,
                "media": None,
                "candidates": [],
            })

    clips.sort(key=lambda c: c["start"])
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
                   aspect: str) -> dict:
    timing_map = {t["paragraph_id"]: t for t in timings}
    return {
        "version": 1,
        "aspect": aspect,
        "duration": round(duration, 3),
        "base": base,
        "cuts": [],
        "clips": build_clips(script["shots"], timing_map, duration),
        "markers": [{"paragraph_id": t["paragraph_id"], "start": round(t["start"], 3),
                     "end": round(t["end"], 3), "estimated": t["estimated"]} for t in timings],
    }


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
