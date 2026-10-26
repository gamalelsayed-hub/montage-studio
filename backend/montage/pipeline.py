"""الخطوات الأوتوماتيك: تفريغ ← مطابقة ← قص تلقائي وترجمة ← تايم لاين ← كلمات بحث ← لقطات."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from . import aligner, captions, edits, imagegen, keywords, media, settings, stock, storage, transcribe
from .jobs import JobContext
from .render import render
from .script_parser import parse_script
from .render import SIZES
from .timeline import build_timeline, merge_cuts, normalize

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
            "has_video": recording["has_video"], "volume": 1.0, "clean_audio": True}
    words = transcript["words"]
    timeline = build_timeline(script, timings, recording["duration"], base, meta["aspect"],
                              pages=storage.list_pages(path),
                              captions=captions.build_captions(words),
                              cuts=edits.auto_cuts(words, recording["duration"]))
    brand = config.get("brand") or {}
    # الترجمة بخط وألوان الهوية
    timeline["caption_style"].update(font=brand.get("font") or timeline["caption_style"]["font"],
                                     box_color=brand.get("primary_color") or timeline["caption_style"]["box_color"])
    shot_clips = [c for c in timeline["clips"] if not c.get("page")]
    skipped = len(script["shots"]) - len(shot_clips)

    ctx.update(0.66, "بكتب كلمات البحث للقطات…")
    queries, source = keywords.make_queries([c["description"] for c in shot_clips],
                                            config["anthropic_api_key"])
    for clip, query in zip(shot_clips, queries):
        clip["query"] = query

    warnings: list[str] = []
    if skipped > 0:
        warnings.append(f"{skipped} لقطة ماتحطتش لأن كلامها مش موجود في التسجيل "
                        "(التسجيل أقصر من السكريبت).")
    estimated = sum(1 for c in shot_clips if c.get("estimated"))
    if estimated:
        warnings.append(f"{estimated} لقطة وقتها متقدّر (متعلّمة بخط متقطع برتقاني). راجع مكانها.")
    if stock.has_key(config):
        total = len(shot_clips) or 1
        for index, clip in enumerate(shot_clips):
            ctx.update(0.7 + 0.29 * index / total, f"بجيب اللقطات ({index + 1}/{total})…")
            if not clip["query"]:
                continue
            try:
                fetch_clip_media(clip, path, meta["aspect"], config)
            except stock.StockError as exc:
                warnings.append(f"{clip['description'][:40]}: {exc}")
            time.sleep(0.3)  # Pixabay بيقفل مؤقتًا لو الطلبات جت ورا بعض بسرعة
    else:
        warnings.append("مفيش مفتاح لقطات، فاللقطات فاضية. حط مفتاح Pixabay من الإعدادات واضغط «هات اللقطات».")
    if source == "dictionary" and timeline["clips"]:
        warnings.append("كلمات البحث اتعملت بالقاموس البسيط. لو حطيت مفتاح Claude هتبقى أدق.")

    storage.write_json(path / "timeline.json", timeline)
    matched = sum(1 for t in timings if not t["estimated"])
    storage.update_meta(project_id, status="ready")
    return {"paragraphs": len(timings), "matched": matched, "clips": len(shot_clips),
            "pages": len(timeline["clips"]) - len(shot_clips), "cuts": len(timeline["cuts"]),
            "captions": len(timeline["captions"]), "keywords": source, "warnings": warnings}


def transcript_words(path: Path) -> list[dict]:
    transcript = storage.read_json(path / "transcript.json")
    if not transcript:
        raise RuntimeError("لسه مافيش تفريغ. اعمل «جهّز الفيديو» الأول.")
    return transcript["words"]


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
    empty = [c for c in timeline["clips"] if not c.get("media") and not c.get("page")]
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
        time.sleep(0.3)
    storage.write_json(path / "timeline.json", timeline)
    return {"filled": sum(1 for c in empty if c.get("media")), "warnings": warnings}


def generate_missing(project_id: str, ctx: JobContext) -> dict:
    """«ولّد بالذكاء الاصطناعي» لكل لقطة لسه فاضية."""
    path = storage.project_dir(project_id)
    meta = storage.read_json(path / "project.json")
    config = settings.load()
    timeline = storage.read_json(path / "timeline.json")
    if not timeline:
        raise RuntimeError("اعمل التجهيز الأوتوماتيك الأول.")
    empty = [c for c in timeline["clips"] if not c.get("media") and not c.get("page")]
    warnings: list[str] = []
    for index, clip in enumerate(empty):
        ctx.update(index / max(len(empty), 1), f"بولّد الصور ({index + 1}/{len(empty)})…")
        try:
            set_generated_media(clip, imagegen.generate(clip["description"], meta["aspect"], config, path / "media"))
        except imagegen.ImageGenError as exc:
            warnings.append(f"{clip['description'][:40]}: {exc}")
            if "مفتاح" in str(exc) or "رصيد" in str(exc):
                break  # مش هينفع في الباقي كمان
        storage.write_json(path / "timeline.json", timeline)  # نحفظ أول بأول عشان الصور غالية
    return {"filled": sum(1 for c in empty if c.get("media")), "warnings": warnings}


def set_generated_media(clip: dict, media_info: dict) -> None:
    if clip.get("kind") != "image" or not clip.get("motion"):
        clip["motion"] = "zoom_in"  # كانت لقطة فيديو: الصورة تاخد زووم بطيء
    clip["media"] = media_info
    clip["kind"] = "image"


def export(project_id: str, ctx: JobContext) -> dict:
    path = storage.project_dir(project_id)
    timeline = storage.read_json(path / "timeline.json")
    if not timeline:
        raise RuntimeError("مفيش تايم لاين لسه.")
    meta = storage.read_json(path / "project.json")
    name = f"{meta['name']}-{timeline['aspect'].replace(':', 'x')}-{time.strftime('%Y%m%d-%H%M%S')}.mp4"
    name = "".join(ch for ch in name if ch not in '\\/:*?"<>|')
    output = path / "exports" / name
    output.parent.mkdir(exist_ok=True)
    timeline = normalize(timeline)
    ctx.update(0.0, "بصدّر الفيديو…")
    render(timeline, path, output, on_progress=lambda f: ctx.update(f, f"بصدّر الفيديو… {int(f * 100)}%"),
           **render_extras(timeline, path, meta))
    return {"file": f"exports/{name}"}


def render_extras(timeline: dict, path: Path, meta: dict) -> dict:
    """الترجمة واللوجو والعنوان (من قالب الهوية في الإعدادات) للتصدير."""
    brand = settings.load().get("brand") or {}
    width, height = SIZES.get(timeline["aspect"], SIZES["9:16"])
    style = dict(timeline["caption_style"])
    if brand.get("font"):
        style.setdefault("font", brand["font"])
    use_brand = timeline.get("brand") or {}
    title = None
    if use_brand.get("title") and meta.get("name"):
        start = 0.0  # لو أول التسجيل مقصوص، العنوان يبدأ من أول جزء ظاهر
        for cut_start, cut_end in merge_cuts(timeline["cuts"], timeline["duration"]):
            if cut_start <= start + 0.05:
                start = cut_end
        title = {"text": meta["name"], "start": start + 0.2, "end": start + 3.2, "font": brand.get("font"),
                 "color": brand.get("text_color") or "#FFFFFF",
                 "box_color": brand.get("accent_color") or brand.get("primary_color")}
    extras: dict = {"fonts_dir": captions.FONTS_DIR}
    if (style.get("enabled") and timeline["captions"]) or title:
        extras["subtitles"] = captions.write_ass(path / "captions.ass", timeline["captions"], style,
                                                 width, height, title)
    logo = settings.brand_logo()
    if use_brand.get("logo", True) and logo:
        extras["logo"] = {"file": logo, "position": brand.get("logo_position", "top-right"),
                          "size": brand.get("logo_size", 0.16), "opacity": brand.get("logo_opacity", 0.9)}
    return extras
