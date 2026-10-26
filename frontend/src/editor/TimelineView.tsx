import { useEffect, useRef } from "react";
import { fileUrl, formatTime } from "../api";
import type { Clip, Timeline } from "../types";
import { moveClip, resizeClip } from "./timelineOps";

export type Selection = { type: "clip" | "cut" | "caption"; id: string } | null;

interface Props {
  projectId: string;
  timeline: Timeline;
  time: number;
  pps: number; // بكسل لكل ثانية
  selection: Selection;
  markIn: number | null;
  paragraphs: Record<string, string>;
  onSeek: (t: number) => void;
  onSelect: (s: Selection) => void;
  onBeginEdit: () => void; // قبل السحب: نقطة رجوع للـ Undo
  onLiveChange: (t: Timeline) => void; // أثناء السحب
}

type Drag = { mode: "move" | "start" | "end"; clip: Clip; originX: number; base: Timeline; moved: boolean };

function tickStep(pps: number): number {
  const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300];
  return steps.find((s) => s * pps >= 70) ?? 600;
}

export default function TimelineView(props: Props) {
  const { projectId, timeline, time, pps, selection, markIn, paragraphs } = props;
  const scroller = useRef<HTMLDivElement>(null);
  const drag = useRef<Drag | null>(null);
  const width = Math.max(timeline.duration * pps, 400);

  // المؤشر يفضل ظاهر وهو بيشتغل
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const x = time * pps;
    if (x < el.scrollLeft + 40 || x > el.scrollLeft + el.clientWidth - 40) {
      el.scrollLeft = Math.max(0, x - el.clientWidth / 3);
    }
  }, [time, pps]);

  const timeAt = (clientX: number) => {
    const el = scroller.current!;
    const rect = el.getBoundingClientRect();
    return Math.max(0, Math.min(timeline.duration, (clientX - rect.left + el.scrollLeft) / pps));
  };

  const startDrag = (event: React.PointerEvent, clip: Clip, mode: Drag["mode"]) => {
    event.stopPropagation();
    (event.target as HTMLElement).setPointerCapture(event.pointerId);
    drag.current = { mode, clip, originX: event.clientX, base: timeline, moved: false };
    props.onSelect({ type: "clip", id: clip.id });
  };

  const onPointerMove = (event: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const delta = (event.clientX - d.originX) / pps;
    if (!d.moved) {
      if (Math.abs(event.clientX - d.originX) < 3) return;
      d.moved = true;
      props.onBeginEdit();
    }
    const next =
      d.mode === "move"
        ? moveClip(d.base, d.clip, d.clip.start + delta)
        : resizeClip(d.base, d.clip, d.mode, (d.mode === "start" ? d.clip.start : d.clip.end) + delta);
    props.onLiveChange(next);
  };

  const onPointerUp = () => {
    drag.current = null;
  };

  const step = tickStep(pps);
  const ticks = [];
  for (let t = 0; t <= timeline.duration; t += step) ticks.push(t);

  return (
    <div className="timeline" dir="ltr">
      <div className="track-labels">
        <div className="ruler-label" />
        <div className="label">لقطات</div>
        <div className="label">التسجيل</div>
        <div className="label captions-label">ترجمة</div>
      </div>
      <div ref={scroller} className="timeline-scroll" onPointerMove={onPointerMove} onPointerUp={onPointerUp}>
        <div className="timeline-inner" style={{ width }}>
          <div className="ruler" onPointerDown={(e) => props.onSeek(timeAt(e.clientX))}>
            {ticks.map((t) => (
              <div key={t} className="tick" style={{ left: t * pps }}>
                {formatTime(t)}
              </div>
            ))}
          </div>

          <div className="track clips-track" onPointerDown={(e) => { props.onSeek(timeAt(e.clientX)); props.onSelect(null); }}>
            {timeline.clips.map((clip) => {
              const selected = selection?.type === "clip" && selection.id === clip.id;
              const thumb = clip.media
                ? clip.media.thumb || (clip.media.kind === "image" ? fileUrl(projectId, `media/${clip.media.file}`) : null)
                : null;
              return (
                <div key={clip.id}
                  className={`clip ${clip.kind} ${selected ? "selected" : ""} ${clip.media ? "" : "empty"} ${clip.estimated ? "estimated" : ""} ${clip.page ? "page" : ""}`}
                  style={{ left: clip.start * pps, width: Math.max((clip.end - clip.start) * pps, 6) }}
                  title={`${clip.estimated ? "⚠️ وقتها متقدّر (الكلام بتاعها ماتلقاش في التسجيل)، راجع مكانها\n" : ""}${clip.description}\n${formatTime(clip.start, true)} → ${formatTime(clip.end, true)}`}
                  onPointerDown={(e) => startDrag(e, clip, "move")}>
                  {clip.estimated && <b className="est">⚠️</b>}
                  {thumb && <img src={thumb} alt="" draggable={false} />}
                  <span dir="rtl">{clip.page ? "📄" : clip.kind === "video" ? "🎞️" : "🖼️"} {clip.description}</span>
                  <div className="handle start" onPointerDown={(e) => startDrag(e, clip, "start")} />
                  <div className="handle end" onPointerDown={(e) => startDrag(e, clip, "end")} />
                </div>
              );
            })}
          </div>

          <div className="track base-track" onPointerDown={(e) => { props.onSeek(timeAt(e.clientX)); props.onSelect(null); }}>
            {timeline.markers.map((m) => (
              <div key={m.paragraph_id} className={`marker ${m.estimated ? "estimated" : ""}`}
                style={{ left: m.start * pps, width: Math.max((m.end - m.start) * pps, 2) }}
                title={(m.estimated ? "(وقت متقدّر) " : "") + (paragraphs[m.paragraph_id] ?? "")}>
                <span dir="rtl">{paragraphs[m.paragraph_id] ?? ""}</span>
              </div>
            ))}
            {timeline.cuts.map((cut) => (
              <div key={cut.id}
                className={`cut ${cut.auto ? "auto" : ""} ${selection?.type === "cut" && selection.id === cut.id ? "selected" : ""}`}
                style={{ left: cut.start * pps, width: Math.max((cut.end - cut.start) * pps, 3) }}
                title={`${cut.auto === "silence" ? "سكتة مقصوصة" : cut.auto === "retake" ? "لغبطة مقصوصة (جملة اتعادت)" : "جزء مقصوص"} (اضغط عليه عشان ترجّعه)`}
                onPointerDown={(e) => { e.stopPropagation(); props.onSelect({ type: "cut", id: cut.id }); }} />
            ))}
          </div>

          <div className="track captions-track" onPointerDown={(e) => { props.onSeek(timeAt(e.clientX)); props.onSelect(null); }}>
            {timeline.captions.map((cap) => (
              <div key={cap.id}
                className={`caption-block ${timeline.caption_style.enabled ? "" : "off"} ${selection?.type === "caption" && selection.id === cap.id ? "selected" : ""}`}
                style={{ left: cap.start * pps, width: Math.max((cap.end - cap.start) * pps, 3) }}
                title={cap.text}
                onPointerDown={(e) => { e.stopPropagation(); props.onSeek(cap.start); props.onSelect({ type: "caption", id: cap.id }); }}>
                <span dir="rtl">{cap.text}</span>
              </div>
            ))}
          </div>

          {markIn !== null && <div className="mark-in" style={{ left: markIn * pps }} />}
          <div className="playhead" style={{ left: time * pps }} />
        </div>
      </div>
    </div>
  );
}
