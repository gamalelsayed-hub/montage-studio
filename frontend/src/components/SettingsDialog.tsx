import { useEffect, useRef, useState } from "react";
import { api, upload } from "../api";
import type { Brand, Settings } from "../types";

export default function SettingsDialog({ onClose }: { onClose: () => void }) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [logoVersion, setLogoVersion] = useState(Date.now());
  const logoInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.get<Settings>("/api/settings").then(setSettings).catch((e) => setMessage(e.message));
  }, []);

  if (!settings) return null;
  const set = (key: keyof Settings, value: string) => setSettings({ ...settings, [key]: value });
  const setBrand = (changes: Partial<Brand>) => setSettings({ ...settings, brand: { ...settings.brand, ...changes } });

  const uploadLogo = async (file: File) => {
    try {
      await upload("/api/brand/logo", file);
      setSettings({ ...settings, has_logo: true });
      setLogoVersion(Date.now());
    } catch (e: any) {
      setMessage(e.message);
    }
  };

  const deleteLogo = async () => {
    await api.del("/api/brand/logo");
    setSettings({ ...settings, has_logo: false });
  };

  const save = async () => {
    setSaving(true);
    try {
      const saved = await api.put<Settings>("/api/settings", settings);
      setSettings({ ...saved, ffmpeg_ok: settings.ffmpeg_ok, has_logo: settings.has_logo, fonts: settings.fonts });
      window.dispatchEvent(new Event("settings-changed"));
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
          مفتاح Gemini (مجاني، اختياري: بيكتب كلمات بحث أدق للقطات)
          <input dir="ltr" value={settings.gemini_api_key}
            onChange={(e) => set("gemini_api_key", e.target.value)} placeholder="AIza..." />
        </label>
        <p className="hint">
          افتح <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a>
          {" "}بحساب جوجل بتاعك ← Create API key ← انسخه. مجاني ومش محتاج فيزا. لو حطيت مفتاح Claude كمان، البرنامج
          بيستخدم Claude الأول.
        </p>

        <label>
          مفتاح Claude (اختياري وبفلوس: بديل لـ Gemini)
          <input dir="ltr" value={settings.anthropic_api_key}
            onChange={(e) => set("anthropic_api_key", e.target.value)} placeholder="sk-ant-..." />
        </label>
        <p className="hint">
          من <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer">console.anthropic.com</a>
          ← API Keys ← Create Key. من غيره البرنامج بيستخدم قاموس بسيط وانت تعدّل كلمة البحث بإيدك.
        </p>

        <label>
          مفتاح OpenAI (اختياري: لتوليد صور بالذكاء الاصطناعي)
          <input dir="ltr" value={settings.openai_api_key}
            onChange={(e) => set("openai_api_key", e.target.value)} placeholder="sk-..." />
        </label>
        <p className="hint">
          من <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer">platform.openai.com/api-keys</a>
          {" "}← Create new secret key. لازم تشحن رصيد من Billing (أقل حاجة 5 دولار)، وOpenAI ممكن يطلب توثيق الحساب
          (Settings ← Organization ← Verify) قبل أول صورة. الصورة الواحدة بحوالي سنت لـ 6 سنت حسب الموديل.
        </p>
        <label>
          موديل الصور
          <select value={settings.openai_image_model} onChange={(e) => set("openai_image_model", e.target.value)}>
            <option value="gpt-image-1-mini">gpt-image-1-mini (أرخص)</option>
            <option value="gpt-image-1">gpt-image-1 (أجود)</option>
          </select>
        </label>

        <h3 className="section-title">🎨 قالب الهوية (لكل الفيديوهات)</h3>
        <div className="row">
          <label className="inline">اللون الأساسي
            <input type="color" value={settings.brand.primary_color} onChange={(e) => setBrand({ primary_color: e.target.value })} />
          </label>
          <label className="inline">لون الكلام
            <input type="color" value={settings.brand.text_color} onChange={(e) => setBrand({ text_color: e.target.value })} />
          </label>
          <label className="inline">لون العنوان
            <input type="color" value={settings.brand.accent_color} onChange={(e) => setBrand({ accent_color: e.target.value })} />
          </label>
        </div>
        <label>
          الخط
          <select value={settings.brand.font} onChange={(e) => setBrand({ font: e.target.value })}>
            {(settings.fonts ?? ["Tajawal", "Cairo"]).map((f) => (
              <option key={f} value={f}>{f === "Tajawal" ? "تجوال (Tajawal)" : f === "Cairo" ? "القاهرة (Cairo)" : f}</option>
            ))}
          </select>
        </label>
        <div className="brand-preview" style={{ fontFamily: settings.brand.font }}>
          <span style={{ background: settings.brand.primary_color, color: settings.brand.text_color }}>الترجمة</span>
          <span style={{ background: settings.brand.accent_color, color: settings.brand.text_color }}>عنوان الفيديو</span>
        </div>
        <div className="row logo-row">
          {settings.has_logo ? (
            <img className="logo-preview" src={`/api/brand/logo?v=${logoVersion}`} alt="اللوجو" />
          ) : (
            <span className="muted">مافيش لوجو.</span>
          )}
          <button className="ghost" onClick={() => logoInput.current?.click()}>📁 {settings.has_logo ? "غيّر اللوجو" : "ارفع لوجو"}</button>
          {settings.has_logo && <button className="danger ghost" onClick={deleteLogo}>شيله</button>}
          <input ref={logoInput} type="file" accept="image/png,image/jpeg,image/webp" hidden
            onChange={(e) => e.target.files?.[0] && uploadLogo(e.target.files[0])} />
        </div>
        <p className="hint">يفضّل PNG بخلفية شفافة. اللوجو بيظهر في ركن الفيديو طول الوقت.</p>
        <div className="row">
          <label>
            مكان اللوجو
            <select value={settings.brand.logo_position}
              onChange={(e) => setBrand({ logo_position: e.target.value as Brand["logo_position"] })}>
              <option value="top-right">فوق يمين</option>
              <option value="top-left">فوق شمال</option>
              <option value="bottom-right">تحت يمين</option>
              <option value="bottom-left">تحت شمال</option>
            </select>
          </label>
          <label>
            حجمه
            <input type="range" min={0.08} max={0.3} step={0.01} value={settings.brand.logo_size}
              onChange={(e) => setBrand({ logo_size: Number(e.target.value) })} />
          </label>
          <label>
            وضوحه
            <input type="range" min={0.3} max={1} step={0.05} value={settings.brand.logo_opacity}
              onChange={(e) => setBrand({ logo_opacity: Number(e.target.value) })} />
          </label>
        </div>

        <h3 className="section-title">التفريغ</h3>
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
