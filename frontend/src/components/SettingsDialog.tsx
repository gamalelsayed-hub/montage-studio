import { useEffect, useState } from "react";
import { api } from "../api";
import type { Settings } from "../types";

export default function SettingsDialog({ onClose }: { onClose: () => void }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.get<Settings>("/api/settings").then(setSettings).catch((e) => setMessage(e.message));
  }, []);

  if (!settings) return null;
  const set = (key: keyof Settings, value: string) => setSettings({ ...settings, [key]: value });

  const save = async () => {
    setSaving(true);
    try {
      const saved = await api.put<Settings>("/api/settings", settings);
      setSettings({ ...saved, ffmpeg_ok: settings.ffmpeg_ok });
      setMessage("اتحفظ ✓");
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>الإعدادات</h2>
        {!settings.ffmpeg_ok && (
          <p className="warn">⚠️ ffmpeg مش لاقيه على الجهاز. شغّل setup.bat تاني (التفاصيل في README).</p>
        )}

        <label>
          مفتاح Pixabay (للقطات المجانية)
          <input dir="ltr" value={settings.pixabay_api_key} onChange={(e) => set("pixabay_api_key", e.target.value)}
            placeholder="الصق المفتاح هنا" />
        </label>
        <p className="hint">
          اعمل حساب مجاني على <a href="https://pixabay.com/" target="_blank" rel="noreferrer">pixabay.com</a>، وبعدين
          افتح <a href="https://pixabay.com/api/docs/" target="_blank" rel="noreferrer">pixabay.com/api/docs</a> وانزل
          لحد «Parameters»، هتلاقي المفتاح مكتوب جنب key باللون الأخضر. انسخه.
        </p>

        <label>
          مفتاح Pexels (اختياري، لو عندك واحد قديم)
          <input dir="ltr" value={settings.pexels_api_key} onChange={(e) => set("pexels_api_key", e.target.value)}
            placeholder="مش لازم" />
        </label>
        <p className="hint">Pexels واقفين إصدار مفاتيح جديدة دلوقتي. لو الاتنين موجودين، البرنامج بيدوّر في Pixabay الأول.</p>

        <label>
          مفتاح Claude (اختياري: بيكتب كلمات بحث أدق للقطات)
          <input dir="ltr" value={settings.anthropic_api_key}
            onChange={(e) => set("anthropic_api_key", e.target.value)} placeholder="sk-ant-..." />
        </label>
        <p className="hint">
          من <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer">console.anthropic.com</a>
          ← API Keys ← Create Key. من غيره البرنامج بيستخدم قاموس بسيط وانت تعدّل كلمة البحث بإيدك.
        </p>

        <div className="row">
          <label>
            موديل التفريغ
            <select value={settings.whisper_model} onChange={(e) => set("whisper_model", e.target.value)}>
              <option value="large-v3">large-v3 (الأدق، محتاج كارت شاشة)</option>
              <option value="turbo">turbo (أسرع، دقة أقل شوية)</option>
              <option value="medium">medium (للأجهزة الأضعف)</option>
            </select>
          </label>
          <label>
            التشغيل على
            <select value={settings.whisper_device} onChange={(e) => set("whisper_device", e.target.value)}>
              <option value="auto">تلقائي (كارت الشاشة، ولو فشل الـ CPU)</option>
              <option value="cuda">كارت الشاشة بس</option>
              <option value="cpu">الـ CPU بس</option>
            </select>
          </label>
        </div>

        <label>
          فولدر المشاريع
          <input dir="ltr" value={settings.projects_dir} onChange={(e) => set("projects_dir", e.target.value)} />
        </label>

        <div className="actions">
          <button className="primary" onClick={save} disabled={saving}>
            حفظ
          </button>
          <button className="ghost" onClick={onClose}>
            قفل
          </button>
          <span className="muted">{message}</span>
        </div>
      </div>
    </div>
  );
}
