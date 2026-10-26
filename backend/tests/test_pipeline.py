"""تجربة الخطوات كلها على السكريبت الحقيقي، مع تفريغ وPexels مزيفين (من غير نت ولا كارت شاشة)."""

import json
import shutil
import subprocess

import pytest

from conftest import fake_transcript
from montage import pipeline, settings, stock, storage, transcribe
from montage.media import probe

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg مش متثبت")


class Ctx:
    def __init__(self):
        self.messages = []

    def update(self, progress=None, message=None):
        self.messages.append((progress, message))


@pytest.fixture
def project(tmp_path, monkeypatch, example_script):
    settings_file = tmp_path / "settings.local.json"
    settings_file.write_text(json.dumps({"projects_dir": str(tmp_path / "projects"),
                                         "pixabay_api_key": "test-key"}), encoding="utf-8")
    monkeypatch.setattr(settings, "SETTINGS_FILE", settings_file)
    meta = storage.create_project("فلوسك حلال ولا حرام", "9:16")
    path = storage.project_dir(meta["id"])
    # أول صفحتين بس عشان التجربة تبقى سريعة
    cut_at = example_script.index("## صفحة ٣")
    (path / "script.md").write_text(example_script[:cut_at], encoding="utf-8")
    return meta["id"], path, tmp_path


@needs_ffmpeg
def test_process_and_export(project, monkeypatch):
    project_id, path, tmp_path = project
    script = pipeline.load_script(path)
    spoken = [p for p in script["paragraphs"]
              if not script["sections"][0]["id"] == p["section_id"]]
    words = fake_transcript(spoken, words_per_second=12)  # كلام سريع عشان الملف يبقى قصير
    duration = words[-1]["end"] + 1
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=f=220:d={duration}", str(path / "recording.wav")], check=True)

    monkeypatch.setattr(transcribe, "transcribe", lambda *a, **k: {
        "language": "ar", "duration": duration, "device": "cpu", "words": words, "segments": []})

    image = tmp_path / "stock.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1080x1920",
                    "-frames:v", "1", str(image)], check=True)
    queries = []

    def fake_search(query, kind, config, aspect="9:16", per_page=8):
        queries.append(query)
        return [{"source": "pixabay", "kind": "image", "id": str(len(queries)), "thumb": None,
                 "url": "https://example.invalid/x.jpg", "author": "test", "page": None}]

    def fake_download(candidate, media_dir):
        media_dir.mkdir(parents=True, exist_ok=True)
        name = f"pixabay_image_{candidate['id']}.jpg"
        shutil.copy(image, media_dir / name)
        return name

    monkeypatch.setattr(stock, "search", fake_search)
    monkeypatch.setattr(stock, "download", fake_download)

    # صورة صفحة ١ من اللوحة
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=1600x1000",
                    "-frames:v", "1", str(path / "media" / "page_1.png")], check=True)

    result = pipeline.process(project_id, Ctx())
    assert result["matched"] == len(spoken)
    assert result["pages"] == 1 and result["captions"] > 0
    timeline = storage.read_json(path / "timeline.json")
    shots = [c for c in timeline["clips"] if not c["page"]]
    assert len(shots) == len(script["shots"]) == 11
    assert all(c["media"] for c in timeline["clips"])
    assert all(c["query"] for c in shots)
    page = next(c for c in timeline["clips"] if c["page"])
    assert page["page"] == 1 and page["fit"] == "contain" and page["media"]["file"] == "page_1.png"
    assert timeline["captions"] and timeline["caption_style"]["enabled"]

    timeline["cuts"] = [{"id": "cut1", "start": 1.0, "end": 2.0}]
    storage.write_json(path / "timeline.json", timeline)
    exported = pipeline.export(project_id, Ctx())
    info = probe(path / exported["file"])
    assert (info["width"], info["height"]) == (1080, 1920)
    assert abs(info["duration"] - (duration - 1.0)) < 0.5
    assert (path / "captions.ass").exists()


def test_find_recording_ignores_info_file(tmp_path):
    (tmp_path / "recording.json").write_text("{}")
    assert storage.find_recording(tmp_path) is None
    (tmp_path / "recording.mov").write_bytes(b"x")
    assert storage.find_recording(tmp_path).name == "recording.mov"


def test_generate_missing_fills_empty_clips(project, monkeypatch):
    from montage import imagegen

    project_id, path, _ = project
    storage.write_json(path / "timeline.json", {
        "aspect": "9:16", "duration": 10, "base": {"file": "a.wav"},
        "clips": [{"id": "a", "description": "سوق قديم", "media": None, "page": None, "motion": "none"},
                  {"id": "b", "description": "خزنة", "media": {"file": "x.jpg"}, "page": None},
                  {"id": "c", "description": "ورشة", "media": None, "page": None}]})
    asked = []

    def fake_generate(description, aspect, config, media_dir):
        asked.append(description)
        if description == "ورشة":
            raise imagegen.ImageGenError("OpenAI رفض الوصف ده.")
        return {"file": "ai_1.png", "kind": "image", "source": "ai"}

    monkeypatch.setattr(imagegen, "generate", fake_generate)
    result = pipeline.generate_missing(project_id, Ctx())
    assert asked == ["سوق قديم", "ورشة"]
    assert result["filled"] == 1 and len(result["warnings"]) == 1
    clips = storage.read_json(path / "timeline.json")["clips"]
    assert clips[0]["media"]["source"] == "ai" and clips[0]["motion"] == "zoom_in"
