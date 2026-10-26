import type { Caption, Clip, Cut, Timeline } from "../types";

export const MIN_CLIP = 0.5;

export const round = (n: number) => Math.round(n * 1000) / 1000;

export function sortedClips(timeline: Timeline): Clip[] {
  return [...timeline.clips].sort((a, b) => a.start - b.start);
}

export function activeClip(timeline: Timeline, time: number): Clip | null {
  return timeline.clips.find((c) => c.media && time >= c.start && time < c.end) ?? null;
}

/** الحدود المسموحة للقطة عشان ماتركبش على جيرانها. */
export function neighbourBounds(timeline: Timeline, clipId: string): [number, number] {
  const clips = sortedClips(timeline);
  const index = clips.findIndex((c) => c.id === clipId);
  const prev = clips[index - 1];
  const next = clips[index + 1];
  return [prev ? prev.end : 0, next ? next.start : timeline.duration];
}

export function updateClip(timeline: Timeline, clipId: string, changes: Partial<Clip>): Timeline {
  return { ...timeline, clips: timeline.clips.map((c) => (c.id === clipId ? { ...c, ...changes } : c)) };
}

export function moveClip(timeline: Timeline, clip: Clip, newStart: number): Timeline {
  const [min, max] = neighbourBounds(timeline, clip.id);
  const length = clip.end - clip.start;
  const start = Math.min(Math.max(newStart, min), Math.max(max - length, min));
  // لو حرّكها بإيده يبقى راجع مكانها
  return updateClip(timeline, clip.id, { start: round(start), end: round(Math.min(start + length, max)), estimated: false });
}

export function resizeClip(timeline: Timeline, clip: Clip, edge: "start" | "end", value: number): Timeline {
  const [min, max] = neighbourBounds(timeline, clip.id);
  if (edge === "start") {
    const start = Math.min(Math.max(value, min), clip.end - MIN_CLIP);
    return updateClip(timeline, clip.id, { start: round(start) });
  }
  const end = Math.max(Math.min(value, max), clip.start + MIN_CLIP);
  return updateClip(timeline, clip.id, { end: round(end) });
}

export function removeClip(timeline: Timeline, clipId: string): Timeline {
  return { ...timeline, clips: timeline.clips.filter((c) => c.id !== clipId) };
}

/** لقطة فاضية جديدة عند مكان المؤشر، في أقرب مساحة فاضية. */
export function addClipAt(timeline: Timeline, time: number): { timeline: Timeline; clip: Clip | null } {
  const clips = sortedClips(timeline);
  let gapStart = 0;
  let gapEnd = timeline.duration;
  for (const c of clips) {
    if (c.end <= time) gapStart = Math.max(gapStart, c.end);
    else if (c.start > time) {
      gapEnd = c.start;
      break;
    } else return { timeline, clip: null }; // المؤشر جوه لقطة
  }
  if (gapEnd - Math.max(time, gapStart) < MIN_CLIP) return { timeline, clip: null };
  const start = Math.max(time, gapStart);
  const clip: Clip = {
    id: `clip_${Date.now().toString(36)}`,
    shot_id: null,
    kind: "image",
    description: "لقطة جديدة",
    query: "",
    start: round(start),
    end: round(Math.min(start + 4, gapEnd)),
    motion: "zoom_in",
    volume: 0,
    fit: "cover",
    estimated: false,
    page: null,
    media: null,
    candidates: [],
  };
  return { timeline: { ...timeline, clips: [...timeline.clips, clip] }, clip };
}

export function addCut(timeline: Timeline, a: number, b: number): Timeline {
  const start = round(Math.max(0, Math.min(a, b)));
  const end = round(Math.min(timeline.duration, Math.max(a, b)));
  if (end - start < 0.05) return timeline;
  const cut: Cut = { id: `cut_${Date.now().toString(36)}`, start, end };
  return { ...timeline, cuts: [...timeline.cuts, cut] };
}

export function removeCut(timeline: Timeline, cutId: string): Timeline {
  return { ...timeline, cuts: timeline.cuts.filter((c) => c.id !== cutId) };
}

/** لو الوقت جوه جزء مقصوص، يرجع نهاية القص عشان المعاينة تنط عليه. */
export function skipCuts(timeline: Timeline, time: number): number {
  let t = time;
  let moved = true;
  while (moved) {
    moved = false;
    for (const cut of timeline.cuts) {
      if (t >= cut.start && t < cut.end - 0.01) {
        t = cut.end;
        moved = true;
      }
    }
  }
  return t;
}

export function keptDuration(timeline: Timeline): number {
  const ranges = [...timeline.cuts].sort((a, b) => a.start - b.start);
  let removed = 0;
  let cursor = 0;
  for (const r of ranges) {
    const s = Math.max(r.start, cursor);
    const e = Math.min(r.end, timeline.duration);
    if (e > s) removed += e - s;
    cursor = Math.max(cursor, e);
  }
  return timeline.duration - removed;
}

/** القص التلقائي الجديد مكان القديم (القص اللي عمله بإيده بيفضل). */
export function replaceAutoCuts(timeline: Timeline, cuts: Cut[]): Timeline {
  return { ...timeline, cuts: [...timeline.cuts.filter((c) => !c.auto), ...cuts] };
}

export function removeAutoCuts(timeline: Timeline): Timeline {
  return { ...timeline, cuts: timeline.cuts.filter((c) => !c.auto) };
}

export function activeCaption(timeline: Timeline, time: number): Caption | null {
  if (!timeline.caption_style.enabled) return null;
  return timeline.captions.find((c) => time >= c.start && time < c.end) ?? null;
}

export function updateCaption(timeline: Timeline, id: string, changes: Partial<Caption>): Timeline {
  return { ...timeline, captions: timeline.captions.map((c) => (c.id === id ? { ...c, ...changes } : c)) };
}

export function removeCaption(timeline: Timeline, id: string): Timeline {
  return { ...timeline, captions: timeline.captions.filter((c) => c.id !== id) };
}
