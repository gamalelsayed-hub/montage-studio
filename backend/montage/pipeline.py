"""الخطوات الأوتوماتيك: تفريغ ← مطابقة ← تايم لاين ← كلمات بحث ← لقطات (Pixabay / Pexels)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from . import aligner, keywords, media, settings, stock, storage, transcribe
from .jobs import JobContext
from .render import render
from .script_parser import parse_script
from .timeline import build_timeline

log = logging.getLogger(__name__)


def load_script(path: Path) -> dict:
    script_md = path / "script.md"
    if not script_md.exists():
        raise RuntimeError("ارفع السكريبت الأول.")
    script = parse_script(script_md.read_text(encoding="utf-8")).to_dict()
    storage.write_json(path / "script.json", script)
    return script


def prepare_recording(path: Path) -> dict:
    """يقرا معلومات التسجيل ويجهّز صوت التفريغ ونسخة المعاينة لو لازم."""
    recording = storage.find_recording(path)
    if recording is None:
        raise RuntimeError("ارفع التسجيل (صوت أو فيديو) الأول.")
    info = media.probe(recording)
    if not info["has_audio"]:
        raise RuntimeError("التسجيل مافيهوش صوت.")
    audio = path / "audio.wav"
    if not audio.exists() or audio.stat().st_mtime < recording.stat().st_mtime:
        media.extract_audio(recording, audio)
    preview = recording
    if recording.suffix.lower() not in media.BROWSER_FRIENDLY:
        preview = path / ("preview.mp4" if info["has_video"] else "preview.m4a")
        if not preview.exists() or preview.stat().st_mtime < recording.stat().st_mtime:
            media.make_preview(recording, preview, info["has_video"])
    info.update(file=recording.name, preview=preview.name)
    storage.write_json(path / "recording.json", info)
    return info


def fetch_clip_media(clip: dict, path: Path, aspect: str, config: dict) -> None:
    """يدوّر على بدائل للقطة وينزّل أول واحدة."""
    clip["candidates"] = stock.search(clip["query"], clip["kind"], config, aspect)
    if clip["kind"] == "video" and not clip["candidates"]:
        # مالقيناش فيديو؟ نجرّب صورة بنفس الكلمات
        clip["candidates"] = stock.search(clip["query"], "image", config, aspect)
    if clip["candidates"]:
        set_clip_media(clip, clip["candidates"][0], path)


def set_clip_media(clip: dict, candidate: dict, path: Path) -> None:
    file_name = stock.download(candidate, path / "media")
    media_info = {"file": file_name, "kind": candidate["kind"], "source": candidate.get("source", "stock"),
                  "id": candidate.get("id"), "thumb": candidate.get("thumb"),
                  "author": candidate.get("author"), "page": candidate.get("page")}
    if candidate["kind"] == "video":
        info = media.probe(path / "media" / file_name)
        media_info.update(duration=info["duration"], has_audio=info["has_audio"])
    clip["media"] = media_info
    clip["kind"] = candidate["kind"]
    if candidate["kind"] == "image" and clip.get("motion") is None:
        clip["motion"] = "zoom_in"


def process(project_id: str, ctx: JobContext, retranscribe: bool = False) -> dict:
    path = storage.project_dir(project_id)
    meta = storage.read_json(path / "project.json")
    config = settings.load()

    ctx.update(0.02, "بقرا السكريبت…")
    script = load_script(path)

    ctx.update(0.05, "بجهّز التسجيل…")
    recording = prepare_recording(path)

    transcript_path = path / "transcript.json"
    transcript = storage.read_json(transcript_path)
    if retranscribe or not transcript:
        ctx.update(0.08, "بفرّغ الكلام (أول مرة بينزّل موديل Whisper وده بياخد وقت)…")
        hint = " ".join(p["text"] for p in script["paragraphs"][:8])
        started = time.time()
        transcript = transcribe.transcribe(
            path / "audio.wav", config["whisper_model"], config["whisper_device"], hint,
            on_progress=lambda f: ctx.update(0.08 + 0.52 * f,
                                             f"بفرّغ الكلام… {int(f * 100)}%"))
        transcript["seconds"] = round(time.time() - started, 1)
        storage.write_json(transcript_path, transcript)

    ctx.update(0.62, "بطابق التفريغ مع السكريبت…")
    timings = aligner.to_dicts(aligner.align(script["paragraphs"], transcript["words"],
                                             recording["duration"]))
    storage.write_json(path / "alignment.json", timings)

    base = {"file": recording["file"], "preview": recording["preview"],
            "has_video": recording["has_video"], "volume": 1.0}
    timeline = build_timeline(script, timings, recording["duration"], base, meta["aspect"])

    ctx.update(0.66, "بكتب كلمات البحث للقطات…")
    queries, source = keywords.make_queries([c["description"] for c in timeline["clips"]],
                                            config["anthropic_api_key"])
    for clip, query in zip(timeline["clips"], queries):
        clip["query"] = query

    warnings: list[str] = []
    if stock.has_key(config):
        total = len(timeline["clips"]) or 1
        for index, clip in enumerate(timeline["clips"]):
            ctx.update(0.7 + 0.29 * index / total, f"بجيب اللقطات ({index + 1}/{total})…")
            if not clip["query"]:
                continue
            try:
                fetch_clip_media(clip, path, meta["aspect"], config)
            except stock.StockError as exc:
                warnings.append(f"{clip['description'][:40]}: {exc}")
    else:
        warnings.append("مفيش مفتاح لقطات، فاللقطات فاضية. حط مفتاح Pixabay من الإعدادات واضغط «هات اللقطات».")
    if source == "dictionary" and timeline["clips"]:
        warnings.append("كلمات البحث اتعملت بالقاموس البسيط. لو حطيت مفتاح Claude هتبقى أدق.")

    storage.write_json(path / "timeline.json", timeline)
    matched = sum(1 for t in timings if not t["estimated"])
    storage.update_meta(project_id, status="ready")
    return {"paragraphs": len(timings), "matched": matched, "clips": len(timeline["clips"]),
            "keywords": source, "warnings": warnings}


def fetch_missing_media(project_id: str, ctx: JobContext) -> dict:
    """«هات اللقطات»: لأي لقطة لسه فاضية (مثلًا بعد ما حط مفتاح اللقطات)."""
    path = storage.project_dir(project_id)
    meta = storage.read_json(path / "project.json")
    config = settings.load()
    if not stock.has_key(config):
        raise RuntimeError(stock.NO_KEY_MESSAGE)
    timeline = storage.read_json(path / "timeline.json")
    if not timeline:
        raise RuntimeError("اعمل التجهيز الأوتوماتيك الأول.")
    empty = [c for c in timeline["clips"] if not c.get("media")]
    need_query = [c for c in empty if not c.get("query")]
    if need_query:
        queries, _ = keywords.make_queries([c["description"] for c in need_query], config["anthropic_api_key"])
        for clip, query in zip(need_query, queries):
            clip["query"] = query
    warnings = []
    for index, clip in enumerate(empty):
        ctx.update(index / max(len(empty), 1), f"بجيب اللقطات ({index + 1}/{len(empty)})…")
        try:
            fetch_clip_media(clip, path, meta["aspect"], config)
        except stock.StockError as exc:
            warnings.append(str(exc))
    storage.write_json(path / "timeline.json", timeline)
    return {"filled": sum(1 for c in empty if c.get("media")), "warnings": warnings}


def export(project_id: str, ctx: JobContext) -> dict:
    path = storage.project_dir(project_id)
    timeline = storage.read_json(path / "timeline.json")
    if not timeline:
        raise RuntimeError("مفيش تايم لاين لسه.")
    meta = storage.read_json(path / "project.json")
    name = f"{meta['name']}-{timeline['aspect'].replace(':', 'x')}-{time.strftime('%Y%m%d-%H%M%S')}.mp4"
    name = "".join(ch for ch in name if ch not in '\\/:*?"<>|')
    output = path / "exports" / name
    ctx.update(0.0, "بصدّر الفيديو…")
    render(timeline, path, output, on_progress=lambda f: ctx.update(f, f"بصدّر الفيديو… {int(f * 100)}%"))
    return {"file": f"exports/{name}"}
