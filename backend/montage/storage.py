"""كل فيديو = مشروع في فولدر لوحده جوه projects/.

projects/<id>/
  project.json     اسم المشروع ومقاسه وحالته
  script.md        السكريبت زي ما اترفع
  recording.*      التسجيل الأصلي (و preview.* لو محتاج نسخة للمتصفح)
  audio.wav        صوت للتفريغ
  transcript.json  التفريغ بالتوقيت
  timeline.json    التايم لاين
  media/           اللقطات المنزّلة، وصور الصفحات (page_N.png)
  captions.ass     ملف الترجمة اللي بيتعمل وقت التصدير
  exports/         الفيديوهات المصدّرة
"""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path

from . import settings


class NotFound(KeyError):
    pass


def _slug(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", name.strip(), flags=re.UNICODE).strip("-")
    return slug[:40] or "project"


def project_dir(project_id: str) -> Path:
    if not re.fullmatch(r"[\w\-]+", project_id, flags=re.UNICODE):
        raise NotFound(project_id)
    path = settings.projects_dir() / project_id
    if not (path / "project.json").exists():
        raise NotFound(project_id)
    return path


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def create_project(name: str, aspect: str) -> dict:
    project_id = f"{_slug(name)}-{uuid.uuid4().hex[:6]}"
    path = settings.projects_dir() / project_id
    (path / "media").mkdir(parents=True)
    (path / "exports").mkdir()
    meta = {"id": project_id, "name": name.strip() or "مشروع جديد", "aspect": aspect,
            "created_at": time.time(), "updated_at": time.time()}
    write_json(path / "project.json", meta)
    return meta


def list_projects() -> list[dict]:
    items = []
    for path in settings.projects_dir().iterdir():
        meta = read_json(path / "project.json")
        if meta:
            items.append(meta)
    return sorted(items, key=lambda m: m.get("updated_at", 0), reverse=True)


def update_meta(project_id: str, **changes) -> dict:
    path = project_dir(project_id) / "project.json"
    meta = read_json(path, {})
    meta.update(changes, updated_at=time.time())
    write_json(path, meta)
    return meta


def delete_project(project_id: str) -> None:
    shutil.rmtree(project_dir(project_id))


RECORDING_TYPES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mp3", ".wav", ".m4a",
                   ".aac", ".ogg", ".flac", ".opus"}


def find_recording(path: Path) -> Path | None:
    """التسجيل الأصلي (من غير recording.json اللي فيه معلوماته)."""
    return next((p for p in sorted(path.glob("recording.*")) if p.suffix.lower() in RECORDING_TYPES), None)


PAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def page_number(file_name: str) -> int | None:
    """رقم الصفحة من اسم الملف: «صفحة 3.png» أو «page_03.jpg» أو «٣.png»."""
    match = re.search(r"\d+", Path(file_name).stem.translate(_DIGITS))
    return int(match.group(0)) if match else None


def list_pages(path: Path) -> dict[int, dict]:
    pages: dict[int, dict] = {}
    for file in sorted((path / "media").glob("page_*")):
        number = page_number(file.name)
        if number is not None and file.suffix.lower() in PAGE_TYPES:
            pages[number] = {"file": file.name, "kind": "image", "source": "page"}
    return pages
