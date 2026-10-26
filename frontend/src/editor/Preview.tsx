import { forwardRef, useEffect, useRef } from "react";
import { fileUrl } from "../api";
import type { Clip, Timeline } from "../types";
import { activeCaption, activeClip } from "./timelineOps";

export interface PreviewBrand {
  logoUrl: string | null;
  logoPosition: string;
  logoSize: number;
  logoOpacity: number;
  title: string | null; // اسم الفيديو (بيظهر لو العنوان شغال في المشروع)
  primary: string;
  accent: string;
  text: string;
  font: string;
}

interface Props {
  projectId: string;
  timeline: Timeline;
  time: number;
  playing: boolean;
  paragraphText: string;
  cueText: string;
  brand?: PreviewBrand;
}

/** المعاينة: التسجيل تحت، واللقطة الحالية فوقه، والترجمة واللوجو بنفس شكل التصدير تقريبًا. */
const Preview = forwardRef<HTMLVideoElement & HTMLAudioElement, Props>(function Preview(
  { projectId, timeline, time, playing, paragraphText, cueText, brand },
  baseRef,
) {
  const clip = activeClip(timeline, time);
  const caption = activeCaption(timeline, time);
  const src = fileUrl(projectId, timeline.base.preview || timeline.base.file);
  const portrait = timeline.aspect === "9:16";
  const frame = useRef<HTMLDivElement>(null);
  const style = timeline.caption_style;

  // الأحجام في التصدير محسوبة على عرض 1080، فبنصغّرها على قد المعاينة
  const frameWidth = frame.current?.clientWidth ?? 360;
  const scale = frameWidth / 1080;
  const captionPos =
    style.position === "top" ? { top: "10%" } : style.position === "middle" ? { top: "45%" } : { bottom: "16%" };
  const showTitle = brand?.title && timeline.brand.title && time < 3.2;
  const logoPos = brand?.logoPosition ?? "top-right";

  return (
    <div ref={frame} className={`preview-frame ${portrait ? "portrait" : "landscape"}`}>
      {timeline.base.has_video ? (
        <video ref={baseRef} src={src} className="base-video" playsInline preload="auto" />
      ) : (
        <>
          <audio ref={baseRef} src={src} preload="auto" />
          <div className="audio-only">
            <p>{caption ? "" : paragraphText || "🎧"}</p>
          </div>
        </>
      )}
      {clip && <Overlay key={clip.id + clip.media!.file} projectId={projectId} clip={clip} time={time} playing={playing} />}
      {brand?.logoUrl && timeline.brand.logo && (
        <img className="preview-logo" src={brand.logoUrl} alt=""
          style={{
            width: `${brand.logoSize * 100}%`, opacity: brand.logoOpacity,
            [logoPos.includes("top") ? "top" : "bottom"]: "4%", [logoPos.includes("left") ? "left" : "right"]: "4%",
          }} />
      )}
      {caption && (
        <div className="caption-overlay" style={{ ...captionPos, fontFamily: style.font, fontSize: style.size * scale, color: style.color }}>
          <span style={style.box ? { background: `${style.box_color}d0` } : { textShadow: "0 0 4px #000, 0 0 2px #000" }}>
            {caption.text}
          </span>
        </div>
      )}
      {showTitle && brand && (
        <div className="preview-title" style={{ fontFamily: brand.font || style.font, fontSize: style.size * 1.35 * scale }}>
          <span style={{ background: brand.accent, color: brand.text }}>{brand.title}</span>
        </div>
      )}
      {cueText && <div className="cue-badge">🗒️ {cueText}</div>}
    </div>
  );
});

function Overlay({ projectId, clip, time, playing }: { projectId: string; clip: Clip; time: number; playing: boolean }) {
  const media = clip.media!;
  const url = fileUrl(projectId, `media/${media.file}`);
  const length = clip.end - clip.start;
  const local = time - clip.start;
  const fade = Math.min(0.3, length / 3);
  const opacity = Math.max(0, Math.min(1, local / fade, (length - local) / fade));
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !video.duration) return;
    const desired = local % video.duration;
    if (Math.abs(video.currentTime - desired) > 0.35) video.currentTime = desired;
    video.volume = Math.min(1, clip.volume || 0);
    video.muted = !(clip.volume > 0);
    if (playing && video.paused) video.play().catch(() => undefined);
    if (!playing && !video.paused) video.pause();
  }, [local, playing, clip.volume]);

  if (clip.fit === "contain") {
    // صورة الصفحة كاملة، ووراها نفسها مضببة (زي التصدير)
    return (
      <div className="fit-wrap" style={{ opacity }}>
        <img src={url} className="fit-bg" alt="" />
        <img src={url} className="fit-fg" alt="" />
      </div>
    );
  }
  if (media.kind === "video") {
    return <video ref={videoRef} src={url} className="overlay" style={{ opacity }} muted playsInline loop preload="auto" />;
  }
  const scale = clip.motion === "zoom_in" ? 1 + 0.1 * Math.min(local / length, 1) : 1;
  return <img src={url} className="overlay" style={{ opacity, transform: `scale(${scale})` }} alt="" />;
}

export default Preview;
