import { useEffect, useState } from "react";
import { api } from "../api";
import type { Aspect, ProjectMeta, Settings } from "../types";

export default function Home({ onOpenSettings }: { onOpenSettings: () => void }) {
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [name, setName] = useState("");
  const [aspect, setAspect] = useState<Aspect>("9:16");
  const [error, setError] = useState("");

  useEffect(() => {
    api.get<ProjectMeta[]>("/api/projects").then(setProjects).catch((e) => setError(e.message));
    api.get<Settings>("/api/settings").then((s) => {
      setSettings(s);
      setAspect(s.default_aspect);
    });
  }, []);

  const create = async () => {
    try {
      const meta = await api.post<ProjectMeta>("/api/projects", { name: name || "فيديو جديد", aspect });
      window.location.hash = `#/p/${encodeURIComponent(meta.id)}`;
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <div className="home">
      {settings && (!(settings.has_pixabay_api_key || settings.has_pexels_api_key) || !settings.ffmpeg_ok) && (
        <div className="banner">
          {!settings.ffmpeg_ok && <div>⚠️ ffmpeg مش متثبت، والتصدير مش هيشتغل. شغّل setup.bat.</div>}
          {!(settings.has_pixabay_api_key || settings.has_pexels_api_key) && (
            <div>
              💡 عشان البرنامج يجيب اللقطات لوحده، حط مفتاح Pixabay المجاني.{" "}
              <button className="link" onClick={onOpenSettings}>افتح الإعدادات</button>
            </div>
          )}
        </div>
      )}

      <section className="card">
        <h2>فيديو جديد</h2>
        <div className="row">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="اسم الفيديو (مثلًا: فلوسك حلال ولا حرام)"
            onKeyDown={(e) => e.key === "Enter" && create()} />
          <div className="segmented">
            <button className={aspect === "9:16" ? "on" : ""} onClick={() => setAspect("9:16")}>📱 طولي 9:16</button>
            <button className={aspect === "16:9" ? "on" : ""} onClick={() => setAspect("16:9")}>🖥️ عرضي 16:9</button>
          </div>
          <button className="primary" onClick={create}>ابدأ</button>
        </div>
      </section>

      <section className="card">
        <h2>المشاريع</h2>
        {error && <p className="error">{error}</p>}
        {projects.length === 0 && <p className="muted">لسه مفيش مشاريع.</p>}
        <ul className="project-list">
          {projects.map((p) => (
            <li key={p.id}>
              <a href={`#/p/${encodeURIComponent(p.id)}`}>
                <strong>{p.name}</strong>
                <span className="muted">
                  {p.aspect} · {new Date(p.updated_at * 1000).toLocaleString("ar-EG")}
                </span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
