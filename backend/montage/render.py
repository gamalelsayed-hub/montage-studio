"""بناء أمر ffmpeg من التايم لاين وتصدير MP4.

الترتيب جوه الفلتر:
1. التسجيل الأساسي يتظبط على مقاس الفيديو (9:16 أو 16:9) بالقص من النص.
   لو التسجيل صوت بس، الخلفية لون كحلي.
2. كل لقطة تتحط فوقه في ثانيتها (overlay) مع ظهور واختفاء ناعم، والصور بزووم بسيط.
3. الأجزاء المقصوصة تتشال من الصورة والصوت في الآخر.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

from .media import _NO_WINDOW, ffmpeg_bin, hardware_encoders
from .timeline import kept_duration, merge_cuts

SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080)}
FPS = 30
FADE = 0.3
BACKGROUND = "0x13202E"


def _fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


def _cover(width: int, height: int) -> str:
    return (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1")


def build_command(timeline: dict, project_dir: Path, output: Path, encoder: str = "libx264") -> list[str]:
    width, height = SIZES.get(timeline.get("aspect", "9:16"), SIZES["9:16"])
    duration = float(timeline["duration"])
    base = timeline["base"]
    base_path = project_dir / base["file"]

    args = [ffmpeg_bin(), "-y", "-hide_banner"]
    filters: list[str] = []

    if base.get("has_video"):
        args += ["-i", str(base_path)]
        filters.append(f"[0:v]{_cover(width, height)},fps={FPS},format=yuv420p[v0]")
        audio_label = "0:a"
        next_input = 1
    else:
        args += ["-f", "lavfi", "-i", f"color=c={BACKGROUND}:s={width}x{height}:r={FPS}:d={_fmt(duration)}",
                 "-i", str(base_path)]
        filters.append("[0:v]format=yuv420p[v0]")
        audio_label = "1:a"
        next_input = 2

    current = "v0"
    clip_audio: list[str] = []
    clips = [c for c in timeline.get("clips", []) if c.get("media") and c["end"] > c["start"]]
    for index, clip in enumerate(sorted(clips, key=lambda c: c["start"])):
        start = max(0.0, float(clip["start"]))
        end = min(float(clip["end"]), duration)
        if end <= start:
            continue
        length = end - start
        media_path = project_dir / "media" / clip["media"]["file"]
        is_video = clip["media"].get("kind", clip["kind"]) == "video"
        if is_video:
            args += ["-stream_loop", "-1", "-t", _fmt(length), "-i", str(media_path)]
        else:
            args += ["-loop", "1", "-framerate", str(FPS), "-t", _fmt(length), "-i", str(media_path)]
        n = next_input
        next_input += 1

        chain = f"[{n}:v]"
        if not is_video and clip.get("motion") == "zoom_in":
            frames = max(int(length * FPS), 1)
            # نكبّر الصورة الأول عشان الزووم مايبقاش مكسّر
            chain += (f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
                      f"crop={width * 2}:{height * 2},"
                      f"zoompan=z='min(1+0.10*on/{frames},1.10)':x='iw/2-(iw/zoom/2)':"
                      f"y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps={FPS},setsar=1")
        else:
            chain += f"{_cover(width, height)},fps={FPS}"
        fade = min(FADE, length / 3)
        chain += (f",format=yuva420p,fade=t=in:st=0:d={_fmt(fade)}:alpha=1,"
                  f"fade=t=out:st={_fmt(length - fade)}:d={_fmt(fade)}:alpha=1,"
                  f"setpts=PTS-STARTPTS+{_fmt(start)}/TB[c{index}]")
        filters.append(chain)
        out = f"v{index + 1}"
        filters.append(f"[{current}][c{index}]overlay=eof_action=pass:"
                       f"enable='between(t,{_fmt(start)},{_fmt(end)})'[{out}]")
        current = out

        volume = float(clip.get("volume") or 0)
        if is_video and volume > 0 and clip["media"].get("has_audio"):
            delay = int(start * 1000)
            filters.append(f"[{n}:a]volume={_fmt(volume)},adelay={delay}|{delay}[ca{index}]")
            clip_audio.append(f"[ca{index}]")

    base_volume = float(base.get("volume", 1.0))
    filters.append(f"[{audio_label}]volume={_fmt(base_volume)}[abase]")
    audio = "abase"
    if clip_audio:
        filters.append(f"[abase]{''.join(clip_audio)}amix=inputs={len(clip_audio) + 1}:"
                       f"duration=first:normalize=0[amixed]")
        audio = "amixed"

    cuts = merge_cuts(timeline.get("cuts", []), duration)
    if cuts:
        expr = "+".join(f"between(t,{_fmt(a)},{_fmt(b)})" for a, b in cuts)
        filters.append(f"[{current}]select='not({expr})',setpts=N/FRAME_RATE/TB[vout]")
        filters.append(f"[{audio}]aselect='not({expr})',asetpts=N/SR/TB[aout]")
    else:
        filters.append(f"[{current}]null[vout]")
        filters.append(f"[{audio}]anull[aout]")

    args += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
             "-t", _fmt(kept_duration(duration, timeline.get("cuts", [])))]
    if encoder == "h264_nvenc":
        args += ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "21", "-b:v", "0", "-pix_fmt", "yuv420p"]
    elif encoder == "h264_qsv":  # كارت Intel
        args += ["-c:v", "h264_qsv", "-preset", "medium", "-global_quality", "22", "-pix_fmt", "nv12"]
    else:
        args += ["-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p"]
    args += ["-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(output)]
    return args


def render(timeline: dict, project_dir: Path, output: Path,
           on_progress: Callable[[float], None] | None = None) -> Path:
    total = kept_duration(float(timeline["duration"]), timeline.get("cuts", [])) or 1.0
    # لو التشفير بالكارت فشل (تعريف قديم مثلًا) نرجع للمعالج
    encoders = hardware_encoders() + ["libx264"]
    last_error = ""
    for encoder in encoders:
        args = build_command(timeline, project_dir, output, encoder)
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
        stderr_tail: list[str] = []

        def read_stderr() -> None:
            for line in process.stderr:  # type: ignore[union-attr]
                stderr_tail.append(line)
                del stderr_tail[:-40]

        import threading
        reader = threading.Thread(target=read_stderr, daemon=True)
        reader.start()
        for line in process.stdout:  # type: ignore[union-attr]
            match = re.match(r"out_time_us=(\d+)", line.strip())
            if match and on_progress:
                on_progress(min(int(match.group(1)) / 1e6 / total, 1.0))
        process.wait()
        reader.join(timeout=5)
        if process.returncode == 0:
            return output
        last_error = "".join(stderr_tail)[-1500:]
    raise RuntimeError(f"فشل التصدير:\n{last_error}")
