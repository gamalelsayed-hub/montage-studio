"""السيرفر المحلي: الـ API والواجهة (React) من نفس العنوان http://127.0.0.1:8765"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import jobs, pexels, pipeline, settings, storage
from .media import FFmpegMissing, ffmpeg_bin

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Montage Studio")
FRONTEND_DIST = settings.ROOT / "frontend" / "dist"
MEDIA_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm"}


def _project(project_id: str) -> Path:
    try:
        return storage.project_dir(project_id)
    except storage.NotFound:
        raise HTTPException(404, "المشروع مش موجود")


def _save_upload(upload: UploadFile, target: Path) -> None:
    with target.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle, length=1 << 20)


# ---------- الإعدادات ----------

@app.get("/api/settings")
def get_settings():
    data = settings.public()
    try:
        ffmpeg_bin()
        data["ffmpeg_ok"] = True
    except FFmpegMissing:
        data["ffmpeg_ok"] = False
    return data


@app.put("/api/settings")
def put_settings(changes: dict = Body(...)):
    return settings.public(settings.save(changes))


# ---------- المشاريع ----------

@app.get("/api/projects")
def list_projects():
    return storage.list_projects()


@app.post("/api/projects")
def create_project(body: dict = Body(...)):
    aspect = body.get("aspect") or settings.load()["default_aspect"]
    if aspect not in ("9:16", "16:9"):
        raise HTTPException(400, "المقاس لازم يبقى 9:16 أو 16:9")
    return storage.create_project(body.get("name", ""), aspect)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str):
    path = _project(project_id)
    script_md = path / "script.md"
    return {
        "meta": storage.read_json(path / "project.json"),
        "script_text": script_md.read_text(encoding="utf-8") if script_md.exists() else "",
        "script": storage.read_json(path / "script.json"),
        "recording": storage.read_json(path / "recording.json"),
        "has_transcript": (path / "transcript.json").exists(),
        "alignment": storage.read_json(path / "alignment.json"),
        "timeline": storage.read_json(path / "timeline.json"),
        "exports": sorted((f"exports/{p.name}" for p in (path / "exports").glob("*.mp4")), reverse=True),
        "jobs": jobs.for_project(project_id),
    }


@app.patch("/api/projects/{project_id}")
def update_project(project_id: str, body: dict = Body(...)):
    path = _project(project_id)
    changes = {k: v for k, v in body.items() if k in ("name", "aspect")}
    if changes.get("aspect") and changes["aspect"] not in ("9:16", "16:9"):
        raise HTTPException(400, "المقاس لازم يبقى 9:16 أو 16:9")
    meta = storage.update_meta(project_id, **changes)
    timeline = storage.read_json(path / "timeline.json")
    if timeline and "aspect" in changes:
        timeline["aspect"] = changes["aspect"]
        storage.write_json(path / "timeline.json", timeline)
    return meta


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str):
    _project(project_id)
    storage.delete_project(project_id)
    return {"ok": True}


@app.put("/api/projects/{project_id}/script")
def put_script(project_id: str, body: dict = Body(...)):
    path = _project(project_id)
    text = body.get("text", "")
    (path / "script.md").write_text(text, encoding="utf-8")
    script = pipeline.load_script(path)
    storage.update_meta(project_id)
    return script


@app.post("/api/projects/{project_id}/recording")
def upload_recording(project_id: str, file: UploadFile = File(...)):
    path = _project(project_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in storage.RECORDING_TYPES:
        raise HTTPException(400, f"نوع الملف {ext or '؟'} مش مدعوم")
    for old in list(path.glob("recording.*")) + list(path.glob("preview.*")):
        old.unlink()
    for stale in ("audio.wav", "transcript.json", "alignment.json", "recording.json"):
        (path / stale).unlink(missing_ok=True)
    _save_upload(file, path / f"recording{ext}")
    try:
        info = pipeline.prepare_recording(path)
    except Exception as exc:
        raise HTTPException(400, str(exc))
    storage.update_meta(project_id)
    return info


@app.post("/api/projects/{project_id}/process")
def process(project_id: str, body: dict = Body(default={})):
    _project(project_id)
    retranscribe = bool(body.get("retranscribe"))
    try:
        return jobs.start(project_id, "process",
                          lambda ctx: pipeline.process(project_id, ctx, retranscribe))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/projects/{project_id}/fetch-media")
def fetch_media(project_id: str):
    _project(project_id)
    try:
        return jobs.start(project_id, "fetch", lambda ctx: pipeline.fetch_missing_media(project_id, ctx))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@app.post("/api/projects/{project_id}/export")
def export(project_id: str):
    _project(project_id)
    try:
        return jobs.start(project_id, "export", lambda ctx: pipeline.export(project_id, ctx))
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "الشغلانة دي مش موجودة")
    return job


# ---------- التايم لاين واللقطات ----------

@app.put("/api/projects/{project_id}/timeline")
def save_timeline(project_id: str, timeline: dict = Body(...)):
    path = _project(project_id)
    if not isinstance(timeline.get("clips"), list) or "duration" not in timeline:
        raise HTTPException(400, "التايم لاين مش سليم")
    storage.write_json(path / "timeline.json", timeline)
    storage.update_meta(project_id)
    return {"ok": True}


@app.get("/api/projects/{project_id}/search")
def search(project_id: str, q: str, kind: str = "image"):
    path = _project(project_id)
    meta = storage.read_json(path / "project.json")
    from .content_rules import apply_to_query
    query = apply_to_query(q)
    try:
        results = pexels.search(query, kind, settings.load()["pexels_api_key"], meta["aspect"], per_page=15)
    except pexels.PexelsError as exc:
        raise HTTPException(400, str(exc))
    return {"query": query, "results": results}


@app.post("/api/projects/{project_id}/clip-media")
def choose_media(project_id: str, body: dict = Body(...)):
    """يختار بديل من Pexels للقطة: ينزّله ويرجع بيانات الملف."""
    path = _project(project_id)
    candidate = body.get("candidate") or {}
    if candidate.get("kind") not in ("image", "video") or not candidate.get("url"):
        raise HTTPException(400, "البديل مش سليم")
    clip: dict = {"kind": candidate["kind"], "motion": None}
    try:
        pipeline.set_clip_media(clip, candidate, path)
    except pexels.PexelsError as exc:
        raise HTTPException(400, str(exc))
    return {"media": clip["media"], "kind": clip["kind"]}


@app.post("/api/projects/{project_id}/upload-media")
def upload_media(project_id: str, file: UploadFile = File(...)):
    """صورة أو فيديو من جهازه بدل لقطة Pexels."""
    path = _project(project_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in MEDIA_TYPES:
        raise HTTPException(400, f"نوع الملف {ext or '؟'} مش مدعوم")
    name = f"upload_{uuid.uuid4().hex[:8]}{ext}"
    (path / "media").mkdir(exist_ok=True)
    _save_upload(file, path / "media" / name)
    kind = "image" if ext in (".jpg", ".jpeg", ".png", ".webp") else "video"
    media_info = {"file": name, "kind": kind, "source": "upload", "thumb": None,
                  "author": None, "page": None}
    if kind == "video":
        from .media import probe
        info = probe(path / "media" / name)
        media_info.update(duration=info["duration"], has_audio=info["has_audio"])
    return {"media": media_info, "kind": kind}


# ---------- الملفات والواجهة ----------

@app.get("/files/{project_id}/{file_path:path}")
def project_file(project_id: str, file_path: str):
    base = _project(project_id).resolve()
    target = (base / file_path).resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(404, "الملف مش موجود")
    return FileResponse(target)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and FRONTEND_DIST.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
