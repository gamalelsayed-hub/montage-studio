"""أدوات ffmpeg/ffprobe: معلومات الملف، واستخراج الصوت، ونسخة للمعاينة."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

BROWSER_FRIENDLY = {".mp4", ".webm", ".mp3", ".wav", ".m4a", ".ogg", ".aac"}
# على ويندوز ماتظهرش شاشة سودا لكل أمر ffmpeg
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class FFmpegMissing(RuntimeError):
    pass


# setup.bat بينزّل ffmpeg هنا لو مش متثبت على الجهاز
LOCAL_FFMPEG = Path(__file__).resolve().parents[2] / "tools" / "ffmpeg" / "bin"


def ffmpeg_bin(name: str = "ffmpeg") -> str:
    path = shutil.which(name) or shutil.which(name, path=str(LOCAL_FFMPEG))
    if not path:
        raise FFmpegMissing(f"{name} مش متثبت أو مش في الـ PATH. شغّل setup.bat تاني.")
    return path


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", creationflags=_NO_WINDOW, **kwargs)


def probe(path: Path) -> dict:
    """يرجع المدة وهل فيه فيديو/صوت والأبعاد."""
    result = run([ffmpeg_bin("ffprobe"), "-v", "error", "-print_format", "json",
                  "-show_format", "-show_streams", str(path)])
    if result.returncode != 0:
        raise RuntimeError(f"الملف مش مقروء: {result.stderr.strip()[:300]}")
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and s.get("disposition", {}).get("attached_pic") != 1), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(data.get("format", {}).get("duration") or 0)
    return {
        "duration": duration,
        "has_video": video is not None,
        "has_audio": audio is not None,
        "width": int(video["width"]) if video else None,
        "height": int(video["height"]) if video else None,
    }


def extract_audio(source: Path, target: Path) -> Path:
    """صوت مونو 16kHz، الشكل اللي Whisper بيحبه."""
    result = run([ffmpeg_bin(), "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
                  "-c:a", "pcm_s16le", str(target)])
    if result.returncode != 0:
        raise RuntimeError(f"فشل استخراج الصوت: {result.stderr.strip()[-300:]}")
    return target


def make_preview(source: Path, target: Path, has_video: bool) -> Path:
    """نسخة خفيفة المتصفح يقدر يشغّلها (لو التسجيل .mov أو .mkv مثلًا)."""
    if has_video:
        args = [ffmpeg_bin(), "-y", "-i", str(source), "-vf", "scale='min(1280,iw)':-2",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-c:a", "aac",
                "-b:a", "128k", "-movflags", "+faststart", str(target)]
    else:
        args = [ffmpeg_bin(), "-y", "-i", str(source), "-vn", "-c:a", "aac", "-b:a", "160k",
                str(target)]
    result = run(args)
    if result.returncode != 0:
        raise RuntimeError(f"فشل تجهيز نسخة المعاينة: {result.stderr.strip()[-300:]}")
    return target


def has_nvenc() -> bool:
    try:
        result = run([ffmpeg_bin(), "-hide_banner", "-encoders"])
    except FFmpegMissing:
        return False
    return "h264_nvenc" in result.stdout
