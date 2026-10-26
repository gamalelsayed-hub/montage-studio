import { forwardRef, useEffect, useRef } from "react";
import { fileUrl } from "../api";
import type { Clip, Timeline } from "../types";
import { activeClip } from "./timelineOps";

interface Props {
  projectId: string;
  timeline: Timeline;
  time: number;
  playing: boolean;
  paragraphText: string;
  cueText: string;
}

/** المعاينة: التسجيل تحت، واللقطة الحالية فوقه بنفس شكل التصدير تقريبًا. */
const Preview = forwardRef<HTMLVideoElement & HTMLAudioElement, Props>(function Preview(
  { projectId, timeline, time, playing, paragraphText, cueText },
  baseRef,
) {
  const clip = activeClip(timeline, time);
  const src = fileUrl(projectId, timeline.base.preview || timeline.base.file);
  const portrait = timeline.aspect === "9:16";

  return (
    <div className={`preview-frame ${portrait ? "portrait" : "landscape"}`}>
      {timeline.base.has_video ? (
        <video ref={baseRef} src={src} className="base-video" playsInline preload="auto" />
      ) : (
        <>
          <audio ref={baseRef} src={src} preload="auto" />
          <div className="audio-only">
            <p>{paragraphText || "🎧"}</p>
          </div>
        </>
      )}
      {clip && <Overlay key={clip.id + clip.media!.file} projectId={projectId} clip={clip} time={time} playing={playing} />}
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

  if (media.kind === "video") {
    return <video ref={videoRef} src={url} className="overlay" style={{ opacity }} muted playsInline loop preload="auto" />;
  }
  const scale = clip.motion === "zoom_in" ? 1 + 0.1 * Math.min(local / length, 1) : 1;
  return <img src={url} className="overlay" style={{ opacity, transform: `scale(${scale})` }} alt="" />;
}

export default Preview;
