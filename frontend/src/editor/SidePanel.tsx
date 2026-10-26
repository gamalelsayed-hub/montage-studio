import { useRef, useState } from "react";
import { api, fileUrl, formatTime } from "../api";
import type { Caption, CaptionStyle, Cut, Timeline } from "../types";
import { keptDuration, removeAutoCuts, replaceAutoCuts } from "./timelineOps";

type Tab = "audio" | "captions" | "pages" | "help";

interface Props {
  projectId: string;
  timeline: Timeline;
  pages: Record<string, string>;
  emptyClips: number;
  busy: boolean;
  onChange: (update: (t: Timeline) => Timeline) => void; // تعديل بنقطة رجوع للـ Undo
  onPagesChange: (pages: Record<string, string>) => void;
  onFetchMedia: () => void;
}

const FONTS = [
  { value: "Tajawal", label: "تجوال (Tajawal)" },
  { value: "Cairo", label: "القاهرة (Cairo)" },
];

/** اللوحة الجانبية لما مافيش حاجة مختارة: الصوت والقص، والترجمة، والصفحات. */
export default function SidePanel(props: Props) {
  const { projectId, timeline, onChange } = props;
  const base = `/api/projects/${encodeURIComponent(projectId)}`;
  const [tab, setTab] = useState<Tab>("audio");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [minGap, setMinGap] = useState(0.8);
  const pagesInput = useRef<HTMLInputElement>(null);

  const run = async (label: string, work: () => Promise<void>) => {
    setBusy(label);
    setError("");
    try {
      await work();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  };

  const autoCuts = timeline.cuts.filter((c) => c.auto);
  const saved = timeline.duration - keptDuration(timeline);
  const style = timeline.caption_style;
  const setStyle = (changes: Partial<CaptionStyle>) =>
    onChange((t) => ({ ...t, caption_style: { ...t.caption_style, ...changes } }));

  const makeCuts = (silence: boolean, retakes: boolean) =>
    run("بيدوّر على السكتات…", async () => {
      const data = await api.post<{ cuts: Cut[] }>(`${base}/auto-cuts`, { silence, retakes, min_gap: minGap });
      onChange((t) => replaceAutoCuts(t, data.cuts));
    });

  const rebuildCaptions = () =>
    run("بيعمل السطور…", async () => {
      if (timeline.captions.length && !confirm("ده هيعمل سطور الترجمة من الأول وأي تعديل عملته فيها هيضيع. أكمّل؟")) return;
      const data = await api.post<{ captions: Caption[] }>(`${base}/captions`, {});
      onChange((t) => ({ ...t, captions: data.captions }));
    });

  const uploadPages = (files: FileList) =>
    run("بيرفع الصفحات…", async () => {
      const form = new FormData();
      Array.from(files).forEach((f) => form.append("files", f));
      const response = await fetch(`${base}/pages`, { method: "POST", body: form });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `خطأ ${response.status}`);
      props.onPagesChange(data.pages);
      if (data.skipped?.length) setError(`ماعرفتش رقم الصفحة من اسم الملف: ${data.skipped.join("، ")}. سمّي الملف برقم الصفحة، مثلًا 3.png`);
    });

  const deletePage = (n: string) =>
    run("بيمسح…", async () => {
      const data = await api.del<{ pages: Record<string, string> }>(`${base}/pages/${n}`);
      props.onPagesChange(data.pages);
    });

  const insertPages = () =>
    run("بيحط الصفحات…", async () => {
      const next = await api.post<Timeline>(`${base}/insert-pages`, timeline);
      onChange(() => next);
    });

  const pageNumbers = Object.keys(props.pages).sort((a, b) => Number(a) - Number(b));

  return (
    <div className="inspector">
      <div className="side-tabs">
        {([
          ["audio", "🔊 الصوت والقص"],
          ["captions", "💬 الترجمة"],
          ["pages", "📄 الصفحات"],
          ["help", "❓ مساعدة"],
        ] as [Tab, string][]).map(([key, label]) => (
          <button key={key} className={tab === key ? "on" : ""} onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>

      {tab === "audio" && (
        <div className="panel-section">
          <label className="check">
            <input type="checkbox" checked={timeline.base.clean_audio}
              onChange={(e) => onChange((t) => ({ ...t, base: { ...t.base, clean_audio: e.target.checked } }))} />
            نضّف صوتي (يقلل الوش، ويخلي الصوت واضح ومستواه ثابت)
          </label>
          <p className="hint small">التنضيف بيتطبق على الفيديو اللي بيتصدّر. المعاينة هنا بالصوت الأصلي.</p>

          <h4>قص السكتات واللغبطة</h4>
          <p className="muted small">
            {autoCuts.length
              ? `فيه ${autoCuts.length} قص تلقائي (سكتات: ${autoCuts.filter((c) => c.auto === "silence").length}، لغبطة: ${autoCuts.filter((c) => c.auto === "retake").length}). الفيديو بقى ${formatTime(keptDuration(timeline))} بدل ${formatTime(timeline.duration)} (وفّرنا ${Math.round(saved)} ثانية).`
              : "مافيش قص تلقائي دلوقتي."}
          </p>
          <label className="inline">اقطع أي سكتة أطول من
            <select value={minGap} onChange={(e) => setMinGap(Number(e.target.value))}>
              <option value={0.5}>نص ثانية</option>
              <option value={0.8}>0.8 ثانية</option>
              <option value={1.2}>ثانية وربع</option>
              <option value={2}>ثانيتين</option>
            </select>
          </label>
          <div className="row">
            <button onClick={() => makeCuts(true, true)} disabled={!!busy}>✂️ اقطع السكتات واللغبطة</button>
            <button onClick={() => makeCuts(true, false)} disabled={!!busy}>السكتات بس</button>
          </div>
          {autoCuts.length > 0 && (
            <button className="ghost" onClick={() => onChange(removeAutoCuts)}>↩️ رجّع كل القص التلقائي</button>
          )}
          <p className="hint small">
            القص البرتقاني في التايم لاين تلقائي، والأحمر انت عملته. اضغط على أي قص عشان ترجّعه لوحده. «اللغبطة» = لما
            تقول جملة وترجع تعيدها، بنشيل المحاولة الأولى.
          </p>
        </div>
      )}

      {tab === "captions" && (
        <div className="panel-section">
          <label className="check">
            <input type="checkbox" checked={style.enabled} onChange={(e) => setStyle({ enabled: e.target.checked })} />
            اعرض الترجمة على الفيديو
          </label>
          <div className="row">
            <label>الخط
              <select value={style.font} onChange={(e) => setStyle({ font: e.target.value })}>
                {FONTS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
              </select>
            </label>
            <label>المكان
              <select value={style.position} onChange={(e) => setStyle({ position: e.target.value as CaptionStyle["position"] })}>
                <option value="bottom">تحت</option>
                <option value="middle">في النص</option>
                <option value="top">فوق</option>
              </select>
            </label>
          </div>
          <label className="inline">الحجم
            <input type="range" min={36} max={110} value={style.size} onChange={(e) => setStyle({ size: Number(e.target.value) })} />
            <span className="small">{style.size}</span>
          </label>
          <div className="row">
            <label className="inline">لون الكلام
              <input type="color" value={style.color} onChange={(e) => setStyle({ color: e.target.value })} />
            </label>
            <label className="inline">
              <input type="checkbox" checked={style.box} onChange={(e) => setStyle({ box: e.target.checked })} />
              خلفية ورا الكلام
            </label>
            {style.box && <input type="color" value={style.box_color} onChange={(e) => setStyle({ box_color: e.target.value })} />}
          </div>
          <p className="muted small">
            فيه {timeline.captions.length} سطر. اضغط على أي سطر في شريط «ترجمة» تحت عشان تصلّح كلامه أو وقته.
          </p>
          <button onClick={rebuildCaptions} disabled={!!busy}>🔄 اعمل السطور من التفريغ من جديد</button>
          <p className="hint small">السطور جاية من تفريغ صوتك، فراجعها: Whisper ساعات بيغلط في كلمة.</p>
        </div>
      )}

      {tab === "pages" && (
        <div className="panel-section">
          <p className="muted small">
            صور صفحات اللوحة: كل صورة بتظهر كاملة في أول القسم «## صفحة N» بتاعها لمدة 4 ثواني. سمّي كل صورة برقم
            الصفحة (مثلًا <code dir="ltr">1.png</code> و <code dir="ltr">2.png</code>).
          </p>
          <button onClick={() => pagesInput.current?.click()} disabled={!!busy}>📁 ارفع صور الصفحات</button>
          <input ref={pagesInput} type="file" accept="image/*" multiple hidden
            onChange={(e) => e.target.files?.length && uploadPages(e.target.files)} />
          {pageNumbers.length > 0 && (
            <>
              <div className="pages-grid">
                {pageNumbers.map((n) => (
                  <figure key={n}>
                    <img src={fileUrl(projectId, `media/${props.pages[n]}`)} alt="" />
                    <figcaption>صفحة {n}</figcaption>
                    <button className="danger" onClick={() => deletePage(n)} title="امسح">×</button>
                  </figure>
                ))}
              </div>
              <button className="primary" onClick={insertPages} disabled={!!busy}>📄 حط الصفحات في التايم لاين</button>
            </>
          )}
        </div>
      )}

      {tab === "help" && (
        <div className="help">
          <ul>
            <li>اضغط على أي لقطة فوق عشان تبدّلها أو تغيّر وقتها.</li>
            <li>اسحب اللقطة عشان تحرّكها، واسحب طرفها عشان تطوّلها أو تقصّرها.</li>
            <li>اللقطة اللي عليها ⚠️ وحواليها خط برتقاني متقطع وقتها متقدّر، لأن كلامها ماتلقاش في التسجيل. راجع مكانها.</li>
            <li>القص: حط المؤشر عند البداية واضغط «بداية القص» (أو I)، وبعدين عند النهاية واضغط «نهاية القص» (أو O).</li>
            <li>مسافة = تشغيل/إيقاف · Ctrl+Z = تراجع · Delete = مسح المختار · الأسهم = ثانية لقدام/لورا.</li>
          </ul>
        </div>
      )}

      {props.emptyClips > 0 && (
        <p className="warn">
          فيه {props.emptyClips} لقطة فاضية.{" "}
          <button className="link" onClick={props.onFetchMedia} disabled={props.busy}>هات اللقطات</button>
        </p>
      )}
      {busy && <p className="muted">{busy}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
