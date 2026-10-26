import { useCallback, useEffect, useRef, useState } from "react";
import { api, fileUrl, formatTime, upload, waitForJob } from "../api";
import Editor from "../editor/Editor";
import type { Job, ProjectData, Script, Settings } from "../types";

export default function ProjectPage({ projectId }: { projectId: string }) {
  const [data, setData] = useState<ProjectData | null>(null);
  const [error, setError] = useState("");
  const [scriptText, setScriptText] = useState("");
  const [scriptDirty, setScriptDirty] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [lastResult, setLastResult] = useState<{ kind: string; result: any } | null>(null);
  const [tab, setTab] = useState<"prepare" | "edit">("prepare");
  const [editorKey, setEditorKey] = useState(0); // بيتغير لما التايم لاين يتعمل من جديد على السيرفر
  const fileInput = useRef<HTMLInputElement>(null);
  const recordingInput = useRef<HTMLInputElement>(null);
  const pagesInput = useRef<HTMLInputElement>(null);

  const base = `/api/projects/${encodeURIComponent(projectId)}`;
  const [settings, setSettings] = useState<Settings | null>(null);
  const [logoVersion, setLogoVersion] = useState(Date.now());

  useEffect(() => {
    const load = () => {
      api.get<Settings>("/api/settings").then(setSettings).catch(() => undefined);
      setLogoVersion(Date.now());
    };
    load();
    window.addEventListener("settings-changed", load);
    return () => window.removeEventListener("settings-changed", load);
  }, []);

  const reload = useCallback(async () => {
    try {
      const fresh = await api.get<ProjectData>(base);
      setData(fresh);
      return fresh;
    } catch (e: any) {
      setError(e.message);
      return null;
    }
  }, [base]);

  useEffect(() => {
    reload().then((fresh) => {
      if (!fresh) return;
      setScriptText(fresh.script_text);
      if (fresh.timeline) setTab("edit");
      const running = fresh.jobs.find((j) => j.status === "running");
      if (running) follow(running);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const follow = async (started: Job) => {
    setJob(started);
    const finished = await waitForJob(started.id, setJob);
    if (finished.status === "done") setLastResult({ kind: finished.kind, result: finished.result });
    const fresh = await reload();
    if (finished.status === "done" && finished.kind !== "export") setEditorKey((k) => k + 1);
    if (finished.status === "done" && finished.kind === "process" && fresh?.timeline) setTab("edit");
    if (finished.status === "done") setJob(null);
  };

  const saveScript = async () => {
    setError("");
    try {
      await api.put<Script>(`${base}/script`, { text: scriptText });
      setScriptDirty(false);
      await reload();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const loadScriptFile = async (file: File) => {
    setScriptText(await file.text());
    setScriptDirty(true);
  };

  const uploadRecording = async (file: File) => {
    setError("");
    setUploadProgress(0);
    try {
      await upload(`${base}/recording`, file, setUploadProgress);
      await reload();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploadProgress(null);
    }
  };

  const uploadPages = async (files: FileList) => {
    setError("");
    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));
    try {
      const response = await fetch(`${base}/pages`, { method: "POST", body: form });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || `خطأ ${response.status}`);
      if (result.skipped?.length) setError(`ماعرفتش رقم الصفحة من اسم الملف: ${result.skipped.join("، ")}. سمّي الملف برقم الصفحة، مثلًا 3.png`);
      setPages(result.pages);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const setPages = (pages: Record<string, string>) => setData((d) => (d ? { ...d, pages } : d));

  const startJob = async (path: string, body: unknown = {}) => {
    setError("");
    setLastResult(null);
    try {
      if (scriptDirty) await saveScript();
      follow(await api.post<Job>(`${base}/${path}`, body));
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (!data) return <div className="page">{error ? <p className="error">{error}</p> : "بيحمّل…"}</div>;

  const script = data.script;
  const busy = job?.status === "running";
  const matched = data.alignment?.filter((a) => !a.estimated).length ?? 0;

  return (
    <div className="page">
      <div className="page-head">
        <h1>{data.meta.name}</h1>
        <span className="pill">{data.meta.aspect === "9:16" ? "📱 طولي 9:16" : "🖥️ عرضي 16:9"}</span>
        <div className="tabs">
          <button className={tab === "prepare" ? "on" : ""} onClick={() => setTab("prepare")}>١. التجهيز</button>
          <button className={tab === "edit" ? "on" : ""} onClick={() => setTab("edit")} disabled={!data.timeline}>
            ٢. المونتاج والتصدير
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {job && (
        <div className={`job ${job.status}`}>
          <div className="job-text">{job.status === "error" ? `❌ ${job.error}` : job.message}</div>
          {job.status === "running" && (
            <div className="progress"><div style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
          )}
          {job.status === "error" && <button className="ghost" onClick={() => setJob(null)}>تمام</button>}
        </div>
      )}
      {lastResult?.kind === "process" && (
        <div className="result">
          ✓ اتطابق {lastResult.result.matched} من {lastResult.result.paragraphs} فقرة، واتحطت {lastResult.result.clips} لقطة
          {lastResult.result.pages ? ` و${lastResult.result.pages} صفحة` : ""}
          {lastResult.result.cuts ? `، واتقص ${lastResult.result.cuts} سكتة/لغبطة` : ""}
          {lastResult.result.captions ? `، واتعمل ${lastResult.result.captions} سطر ترجمة` : ""}.
          {lastResult.result.warnings?.map((w: string) => <div key={w} className="warn">⚠️ {w}</div>)}
        </div>
      )}

      {tab === "prepare" && (
        <div className="prepare">
          <section className="card">
            <div className="card-head">
              <h2>السكريبت</h2>
              <button className="ghost" onClick={() => fileInput.current?.click()}>📄 افتح ملف .md</button>
              <input ref={fileInput} type="file" accept=".md,.txt,text/markdown,text/plain" hidden
                onChange={(e) => e.target.files?.[0] && loadScriptFile(e.target.files[0])} />
              <button className="primary" disabled={!scriptDirty} onClick={saveScript}>حفظ السكريبت</button>
            </div>
            <textarea className="script-box" value={scriptText} dir="rtl"
              placeholder={"الصق السكريبت هنا…\n\n## صفحة ١: العنوان\n\nالكلام اللي هتقوله.\n\n**[صورة]** وصف اللقطة"}
              onChange={(e) => { setScriptText(e.target.value); setScriptDirty(true); }} />
            {script && !scriptDirty && (
              <p className="muted">
                فيه {script.sections.length} قسم، و{script.paragraphs.length} فقرة كلام، و{script.shots.length} لقطة
                ({script.shots.filter((s) => s.kind === "video").length} فيديو)، و{script.cues.length} ملاحظة.
              </p>
            )}
          </section>

          <section className="card">
            <div className="card-head">
              <h2>التسجيل</h2>
              <button className="ghost" onClick={() => recordingInput.current?.click()} disabled={uploadProgress !== null}>
                🎙️ {data.recording ? "غيّر التسجيل" : "ارفع التسجيل (صوت أو فيديو)"}
              </button>
              <input ref={recordingInput} type="file" accept="audio/*,video/*" hidden
                onChange={(e) => e.target.files?.[0] && uploadRecording(e.target.files[0])} />
            </div>
            {uploadProgress !== null && (
              <div className="progress"><div style={{ width: `${Math.round(uploadProgress * 100)}%` }} /></div>
            )}
            {data.recording && (
              <div className="recording">
                <span>{data.recording.has_video ? "🎥 فيديو" : "🎧 صوت بس"} · {formatTime(data.recording.duration)}</span>
                {data.recording.has_video ? (
                  <video src={fileUrl(projectId, data.recording.preview)} controls preload="metadata" />
                ) : (
                  <audio src={fileUrl(projectId, data.recording.preview)} controls preload="metadata" />
                )}
              </div>
            )}
          </section>

          <section className="card">
            <div className="card-head">
              <h2>صور صفحات اللوحة (اختياري)</h2>
              <button className="ghost" onClick={() => pagesInput.current?.click()}>📄 ارفع الصور</button>
              <input ref={pagesInput} type="file" accept="image/*" multiple hidden
                onChange={(e) => e.target.files?.length && uploadPages(e.target.files)} />
            </div>
            <p className="muted small">
              كل صورة بتظهر في أول القسم «## صفحة N» بتاعها. سمّي الصور بأرقام الصفحات (1.png و2.png …).
              {Object.keys(data.pages ?? {}).length > 0 && ` مرفوع: صفحة ${Object.keys(data.pages).sort((a, b) => Number(a) - Number(b)).join("، ")}.`}
            </p>
          </section>

          <section className="card">
            <h2>التجهيز الأوتوماتيك</h2>
            <p className="muted">
              البرنامج هيفرّغ كلامك، ويطابقه مع السكريبت، ويجيب لكل [صورة] و[فيديو] لقطة من Pixabay ويحطها في ثانيتها،
              ويقص السكتات واللغبطة، ويعمل الترجمة، ويحط صور الصفحات.
            </p>
            {data.alignment && (
              <p className="muted">آخر مطابقة: {matched} من {data.alignment.length} فقرة اتلقت في التسجيل.</p>
            )}
            <div className="actions">
              <button className="primary big" disabled={busy || !script || !data.recording || scriptDirty && !scriptText}
                onClick={() => {
                  if (data.timeline && !confirm("ده هيعمل التايم لاين من الأول وتعديلاتك هتضيع. أكمّل؟")) return;
                  startJob("process");
                }}>
                ✨ {data.timeline ? "جهّز من الأول" : "جهّز الفيديو"}
              </button>
              {data.has_transcript && (
                <button className="ghost" disabled={busy} onClick={() => {
                  if (data.timeline && !confirm("ده هيعمل التايم لاين من الأول وتعديلاتك هتضيع. أكمّل؟")) return;
                  startJob("process", { retranscribe: true });
                }}>
                  فرّغ الكلام تاني
                </button>
              )}
            </div>
            {(!script || !data.recording) && (
              <p className="hint">محتاج {!script ? "تحفظ السكريبت" : ""}{!script && !data.recording ? " و" : ""}
                {!data.recording ? "ترفع التسجيل" : ""} الأول.</p>
            )}
          </section>
        </div>
      )}

      {tab === "edit" && data.timeline && (
        <Editor
          key={editorKey}
          projectId={projectId}
          initial={data.timeline}
          script={data.script}
          pages={data.pages ?? {}}
          onPagesChange={setPages}
          exports={data.exports}
          busy={busy}
          onExport={() => startJob("export")}
          onFetchMedia={() => startJob("fetch-media")}
          onGenerateMissing={() => startJob("generate-missing")}
          brandSettings={settings?.brand ?? null}
          hasLogo={!!settings?.has_logo}
          hasOpenAI={!!settings?.has_openai_api_key}
          brand={settings ? {
            logoUrl: settings.has_logo ? `/api/brand/logo?v=${logoVersion}` : null,
            logoPosition: settings.brand.logo_position,
            logoSize: settings.brand.logo_size,
            logoOpacity: settings.brand.logo_opacity,
            title: data.meta.name,
            primary: settings.brand.primary_color,
            accent: settings.brand.accent_color,
            text: settings.brand.text_color,
            font: settings.brand.font,
          } : undefined}
          lastExport={lastResult?.kind === "export" ? lastResult.result.file : null}
        />
      )}
    </div>
  );
}
