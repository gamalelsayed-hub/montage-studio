import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, fileUrl, formatTime } from "../api";
import type { Aspect, Clip, Script, Timeline } from "../types";
import Inspector from "./Inspector";
import Preview from "./Preview";
import TimelineView, { type Selection } from "./TimelineView";
import { addClipAt, addCut, keptDuration, removeClip, removeCut, round, skipCuts, updateClip } from "./timelineOps";
import { useHistory } from "./useHistory";

interface Props {
  projectId: string;
  initial: Timeline;
  script: Script | null;
  exports: string[];
  busy: boolean;
  lastExport: string | null;
  onExport: () => void;
  onFetchMedia: () => void;
}

export default function Editor({ projectId, initial, script, exports, busy, lastExport, onExport, onFetchMedia }: Props) {
  const history = useHistory<Timeline>(initial);
  const timeline = history.present;
  const base = `/api/projects/${encodeURIComponent(projectId)}`;

  const mediaRef = useRef<HTMLVideoElement & HTMLAudioElement>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [pps, setPps] = useState(40);
  const [selection, setSelection] = useState<Selection>(null);
  const [markIn, setMarkIn] = useState<number | null>(null);
  const [saveState, setSaveState] = useState<"saved" | "pending" | "saving" | "error">("saved");

  // ---------- الحفظ التلقائي ----------
  const firstRender = useRef(true);
  const saveTimer = useRef<number>();
  const latest = useRef(timeline);
  latest.current = timeline;

  const saveNow = useCallback(async () => {
    window.clearTimeout(saveTimer.current);
    setSaveState("saving");
    try {
      await api.put(`${base}/timeline`, latest.current);
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  }, [base]);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    setSaveState("pending");
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(saveNow, 800);
  }, [timeline, saveNow]);

  // ---------- التشغيل ----------
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    const tick = () => {
      const media = mediaRef.current;
      if (media) {
        const skipped = skipCuts(latest.current, media.currentTime);
        if (skipped !== media.currentTime) media.currentTime = skipped;
        setTime(skipped);
        if (media.ended) setPlaying(false);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing]);

  useEffect(() => {
    const media = mediaRef.current;
    if (media) media.volume = Math.min(1, timeline.base.volume);
  }, [timeline.base.volume]);

  const togglePlay = useCallback(() => {
    const media = mediaRef.current;
    if (!media) return;
    if (media.paused) {
      media.currentTime = skipCuts(latest.current, media.currentTime);
      media.play().then(() => setPlaying(true)).catch(() => undefined);
    } else {
      media.pause();
      setPlaying(false);
    }
  }, []);

  const seek = useCallback((t: number) => {
    const clamped = Math.max(0, Math.min(t, latest.current.duration));
    if (mediaRef.current) mediaRef.current.currentTime = clamped;
    setTime(clamped);
  }, []);

  // ---------- التعديلات ----------
  const selectedClip = selection?.type === "clip" ? timeline.clips.find((c) => c.id === selection.id) ?? null : null;

  const changeClip = (clip: Clip, changes: Partial<Clip>) => {
    const next = { ...changes };
    if (next.start !== undefined) next.start = round(Math.min(next.start, (next.end ?? clip.end) - 0.5));
    if (next.end !== undefined) next.end = round(Math.min(Math.max(next.end, (next.start ?? clip.start) + 0.5), timeline.duration));
    history.set((t) => updateClip(t, clip.id, next));
  };

  const deleteSelection = useCallback(() => {
    if (!selection) return;
    history.set((t) => (selection.type === "clip" ? removeClip(t, selection.id) : removeCut(t, selection.id)));
    setSelection(null);
  }, [selection, history]);

  const addClip = () => {
    const result = addClipAt(latest.current, time);
    if (!result.clip) {
      alert("حط المؤشر في مكان فاضي من غير لقطات الأول.");
      return;
    }
    history.set(result.timeline);
    setSelection({ type: "clip", id: result.clip.id });
  };

  const markCutStart = () => setMarkIn(time);
  const markCutEnd = () => {
    if (markIn === null) return;
    history.set((t) => addCut(t, markIn, time));
    setMarkIn(null);
  };

  const setAspect = async (aspect: Aspect) => {
    history.set((t) => ({ ...t, aspect }));
    await api.patch(base, { aspect }).catch(() => undefined);
  };

  // ---------- الكيبورد ----------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      const ctrl = e.ctrlKey || e.metaKey;
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      } else if (ctrl && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        history.undo();
      } else if (ctrl && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
        e.preventDefault();
        history.redo();
      } else if (e.key === "Delete" || e.key === "Backspace") {
        deleteSelection();
      } else if (e.key === "ArrowRight") {
        seek(time + (e.shiftKey ? 5 : 1));
      } else if (e.key === "ArrowLeft") {
        seek(time - (e.shiftKey ? 5 : 1));
      } else if (e.key.toLowerCase() === "i") {
        setMarkIn(time);
      } else if (e.key.toLowerCase() === "o" && markIn !== null) {
        history.set((t) => addCut(t, markIn, time));
        setMarkIn(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay, history, deleteSelection, seek, time, markIn]);

  // ---------- النص الحالي من السكريبت ----------
  const paragraphs = useMemo(() => {
    const map: Record<string, string> = {};
    script?.paragraphs.forEach((p) => (map[p.id] = p.text));
    return map;
  }, [script]);

  const currentMarker = timeline.markers.find((m) => time >= m.start && time < m.end);
  const paragraphText = currentMarker ? paragraphs[currentMarker.paragraph_id] ?? "" : "";
  const cueText = useMemo(() => {
    if (!currentMarker || !script) return "";
    return script.cues
      .filter((c) => c.paragraph_id === currentMarker.paragraph_id)
      .map((c) => c.text)
      .join(" · ");
  }, [currentMarker, script]);

  const emptyClips = timeline.clips.filter((c) => !c.media).length;
  const exportNow = async () => {
    await saveNow();
    onExport();
  };
  const fetchNow = async () => {
    await saveNow();
    onFetchMedia();
  };

  return (
    <div className="editor">
      <div className="editor-top">
        <div className="preview-col">
          <Preview ref={mediaRef} projectId={projectId} timeline={timeline} time={time} playing={playing}
            paragraphText={paragraphText} cueText={cueText} />
          <div className="transport">
            <button className="primary round" onClick={togglePlay} title="مسافة">{playing ? "⏸" : "▶"}</button>
            <span className="clock" dir="ltr">{formatTime(time, true)} / {formatTime(timeline.duration)}</span>
            <span className="muted small">بعد القص: {formatTime(keptDuration(timeline))}</span>
          </div>
          {paragraphText && timeline.base.has_video && <p className="now-text">{paragraphText}</p>}
        </div>

        <div className="side-col">
          {selectedClip ? (
            <Inspector key={selectedClip.id} projectId={projectId} clip={selectedClip}
              onChange={(changes) => changeClip(selectedClip, changes)}
              onDelete={deleteSelection} />
          ) : selection?.type === "cut" ? (
            <div className="inspector">
              <h3>✂️ جزء مقصوص</h3>
              <p className="muted">الجزء ده مش هيظهر في الفيديو النهائي.</p>
              <button onClick={deleteSelection}>↩️ رجّع الجزء ده</button>
            </div>
          ) : (
            <div className="inspector help">
              <h3>إزاي تعدّل</h3>
              <ul>
                <li>اضغط على أي لقطة فوق عشان تبدّلها أو تغيّر وقتها.</li>
                <li>اسحب اللقطة عشان تحرّكها، واسحب طرفها عشان تطوّلها أو تقصّرها.</li>
                <li>القص: حط المؤشر عند البداية واضغط «بداية القص» (أو I)، وبعدين عند النهاية واضغط «نهاية القص» (أو O).</li>
                <li>مسافة = تشغيل/إيقاف · Ctrl+Z = تراجع · Delete = مسح المختار · الأسهم = ثانية لقدام/لورا.</li>
              </ul>
              {emptyClips > 0 && (
                <p className="warn">
                  فيه {emptyClips} لقطة فاضية.{" "}
                  <button className="link" onClick={fetchNow} disabled={busy}>هات اللقطات من Pexels</button>
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="toolbar">
        <button onClick={history.undo} disabled={!history.canUndo} title="Ctrl+Z">↶ تراجع</button>
        <button onClick={history.redo} disabled={!history.canRedo} title="Ctrl+Y">↷ إعادة</button>
        <span className="sep" />
        <button onClick={addClip}>➕ لقطة هنا</button>
        <button onClick={markCutStart} title="I">✂️ بداية القص</button>
        <button onClick={markCutEnd} disabled={markIn === null} title="O">✂️ نهاية القص</button>
        {markIn !== null && <button className="ghost" onClick={() => setMarkIn(null)}>إلغاء</button>}
        <span className="sep" />
        <label className="inline">🔊 صوت التسجيل
          <input type="range" min={0} max={2} step={0.05} value={timeline.base.volume}
            onPointerDown={history.checkpoint}
            onChange={(e) => history.set((t) => ({ ...t, base: { ...t.base, volume: Number(e.target.value) } }), false)} />
          <span className="small">{Math.round(timeline.base.volume * 100)}%</span>
        </label>
        <label className="inline">🔍
          <input type="range" min={5} max={200} value={pps} onChange={(e) => setPps(Number(e.target.value))} />
        </label>
        <span className={`save-state ${saveState}`}>
          {saveState === "saved" ? "✓ محفوظ" : saveState === "error" ? "⚠️ الحفظ فشل" : "بيحفظ…"}
        </span>
      </div>

      <TimelineView projectId={projectId} timeline={timeline} time={time} pps={pps} selection={selection}
        markIn={markIn} paragraphs={paragraphs} onSeek={seek} onSelect={setSelection}
        onBeginEdit={history.checkpoint} onLiveChange={(t) => history.set(t, false)} />

      <section className="card export">
        <div className="card-head">
          <h2>التصدير</h2>
          <div className="segmented">
            <button className={timeline.aspect === "9:16" ? "on" : ""} onClick={() => setAspect("9:16")}>📱 9:16</button>
            <button className={timeline.aspect === "16:9" ? "on" : ""} onClick={() => setAspect("16:9")}>🖥️ 16:9</button>
          </div>
          <button className="primary big" onClick={exportNow} disabled={busy}>⬇️ صدّر MP4</button>
        </div>
        {lastExport && (
          <video className="export-video" src={fileUrl(projectId, lastExport)} controls preload="metadata" />
        )}
        {exports.length > 0 && (
          <ul className="exports">
            {exports.map((path) => (
              <li key={path}>
                <a href={fileUrl(projectId, path)} download>{path.replace("exports/", "")}</a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
