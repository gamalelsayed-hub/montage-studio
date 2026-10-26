import { useRef, useState } from "react";
import { api, fileUrl, formatTime, upload } from "../api";
import type { Candidate, Clip, ClipMedia } from "../types";

interface Props {
  projectId: string;
  clip: Clip;
  onChange: (changes: Partial<Clip>) => void;
  onDelete: () => void;
}

/** لوحة اللقطة المختارة: الوقت، والتبديل بلقطة تانية، والتحريك، والصوت. */
export default function Inspector({ projectId, clip, onChange, onDelete }: Props) {
  const base = `/api/projects/${encodeURIComponent(projectId)}`;
  const [query, setQuery] = useState(clip.query);
  const [kind, setKind] = useState<"image" | "video">(clip.kind);
  const [results, setResults] = useState<Candidate[]>(clip.candidates);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const search = async () => {
    setBusy("بيدوّر…");
    setError("");
    try {
      const data = await api.get<{ query: string; results: Candidate[] }>(
        `${base}/search?q=${encodeURIComponent(query)}&kind=${kind}`,
      );
      setResults(data.results);
      onChange({ query: data.query, candidates: data.results });
      setQuery(data.query);
      if (!data.results.length) setError("مالقيتش نتايج. جرّب كلمات تانية بالإنجليزي.");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const choose = async (candidate: Candidate) => {
    setBusy("بينزّل اللقطة…");
    setError("");
    try {
      const data = await api.post<{ media: ClipMedia; kind: "image" | "video" }>(`${base}/clip-media`, { candidate });
      onChange({ media: data.media, kind: data.kind, motion: data.kind === "image" ? clip.motion ?? "zoom_in" : "none" });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const uploadOwn = async (file: File) => {
    setBusy("بيرفع…");
    setError("");
    try {
      const data = await upload<{ media: ClipMedia; kind: "image" | "video" }>(`${base}/upload-media`, file);
      onChange({ media: data.media, kind: data.kind, motion: data.kind === "image" ? "zoom_in" : "none" });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const generate = async () => {
    setBusy("بيولّد الصورة (من 10 لـ 40 ثانية)…");
    setError("");
    try {
      const data = await api.post<{ media: ClipMedia; kind: "image" }>(`${base}/generate-image`, { description: clip.description });
      onChange({ media: data.media, kind: "image", motion: clip.motion && clip.motion !== "none" ? clip.motion : "zoom_in" });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const setTime = (edge: "start" | "end", value: string) => {
    const seconds = Number(value);
    if (Number.isFinite(seconds)) onChange({ [edge]: Math.max(0, seconds) } as Partial<Clip>);
  };

  return (
    <div className="inspector">
      <div className="card-head">
        <h3>{clip.kind === "video" ? "🎞️ لقطة فيديو" : "🖼️ صورة"}</h3>
        <button className="danger ghost" onClick={onDelete}>🗑️ امسح اللقطة</button>
      </div>
      {clip.estimated && (
        <div className="estimate-note">
          ⚠️ الكلام اللي اللقطة دي مربوطة بيه ماتلقاش في التسجيل، فمكانها متقدّر. اسمع واتأكد إنها في المكان الصح.{" "}
          <button className="link" onClick={() => onChange({ estimated: false })}>✓ راجعتها</button>
        </div>
      )}
      {clip.page !== null && clip.page !== undefined && (
        <p className="muted small">📄 صورة صفحة {clip.page} من اللوحة. بتظهر كاملة فوق نسخة مضببة منها.</p>
      )}
      <textarea className="desc" value={clip.description} rows={2}
        onChange={(e) => onChange({ description: e.target.value })} />

      <div className="row times">
        <label>من (ثانية)
          <input type="number" step="0.1" value={clip.start} onChange={(e) => setTime("start", e.target.value)} />
        </label>
        <label>لحد (ثانية)
          <input type="number" step="0.1" value={clip.end} onChange={(e) => setTime("end", e.target.value)} />
        </label>
        <span className="muted">المدة {formatTime(clip.end - clip.start, true)}</span>
      </div>

      {clip.media?.kind === "image" && (
        <label className="check">
          <input type="checkbox" checked={clip.fit === "contain"}
            onChange={(e) => onChange({ fit: e.target.checked ? "contain" : "cover" })} />
          اعرض الصورة كاملة من غير قص (مناسب للصفحات والجداول)
        </label>
      )}
      {clip.media?.kind === "image" && clip.fit !== "contain" && (
        <label className="check">
          <input type="checkbox" checked={clip.motion === "zoom_in"}
            onChange={(e) => onChange({ motion: e.target.checked ? "zoom_in" : "none" })} />
          زووم بطيء على الصورة
        </label>
      )}
      {clip.media?.kind === "video" && clip.media.has_audio && (
        <label>صوت اللقطة
          <input type="range" min={0} max={1} step={0.05} value={clip.volume}
            onChange={(e) => onChange({ volume: Number(e.target.value) })} />
        </label>
      )}
      {clip.media && (
        <p className="muted small">
          الحالية: {clip.media.source === "upload" ? "من جهازك" : clip.media.source === "ai" ? "🎨 متولّدة بالذكاء الاصطناعي"
            : clip.media.source === "page" ? "صفحة من اللوحة"
              : `${clip.media.source === "pixabay" ? "Pixabay" : "Pexels"}${clip.media.author ? ` · ${clip.media.author}` : ""}`}
          {clip.media.page && <> · <a href={clip.media.page} target="_blank" rel="noreferrer">المصدر</a></>}
        </p>
      )}

      <h4>بدّل اللقطة</h4>
      <div className="row">
        <input dir="ltr" value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()} placeholder="كلمات بحث بالإنجليزي" />
        <select value={kind} onChange={(e) => setKind(e.target.value as "image" | "video")}>
          <option value="image">صور</option>
          <option value="video">فيديو</option>
        </select>
        <button onClick={search} disabled={!!busy}>🔎 دوّر</button>
      </div>
      <div className="row">
        <button className="ghost" onClick={() => fileInput.current?.click()} disabled={!!busy}>📁 من جهازي</button>
        <input ref={fileInput} type="file" accept="image/*,video/*" hidden
          onChange={(e) => e.target.files?.[0] && uploadOwn(e.target.files[0])} />
        {busy && <span className="muted">{busy}</span>}
      </div>
      <div className="ai-box">
        <h4>🎨 ولّد صورة بالذكاء الاصطناعي</h4>
        <p className="muted small">
          بيرسم صورة من وصف اللقطة اللي فوق (عدّله لو حابب). مفيد لما Pixabay مايلاقيش حاجة مناسبة. محتاج مفتاح OpenAI
          في الإعدادات، والصورة بحوالي سنت لـ 6 سنت.
        </p>
        <button onClick={generate} disabled={!!busy || !clip.description.trim()}>🎨 ولّد صورة</button>
      </div>
      <p className="hint small">راجع إن أي ست في اللقطة محجبة ولابسة لبس شرعي.</p>
      {error && <p className="error">{error}</p>}
      <div className="candidates">
        {results.map((c) => {
          const current = clip.media?.id === c.id && clip.media?.source === c.source;
          return (
            <button key={`${c.kind}${c.id}`} className={`candidate ${current ? "current" : ""}`}
              onClick={() => choose(c)} disabled={!!busy} title={c.author ?? ""}>
              {c.thumb ? <img src={c.thumb} alt="" loading="lazy" /> : <span>؟</span>}
              {c.kind === "video" && <em>🎞️ {c.duration ? `${c.duration}ث` : ""}</em>}
            </button>
          );
        })}
      </div>
      {clip.media?.source === "upload" && clip.media.kind === "image" && (
        <img className="own-preview" src={fileUrl(projectId, `media/${clip.media.file}`)} alt="" />
      )}
    </div>
  );
}
