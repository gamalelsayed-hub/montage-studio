import json

from fastapi.testclient import TestClient

from montage import pipeline, settings, storage


def _settings(tmp_path, monkeypatch, **extra):
    settings_file = tmp_path / "settings.local.json"
    settings_file.write_text(json.dumps({"projects_dir": str(tmp_path / "projects"), **extra}), encoding="utf-8")
    monkeypatch.setattr(settings, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(settings, "BRAND_DIR", tmp_path / "brand")


def test_logo_upload_and_delete(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    from montage.api import app

    client = TestClient(app)
    assert client.get("/api/settings").json()["has_logo"] is False
    response = client.post("/api/brand/logo", files={"file": ("logo.png", b"\x89PNG", "image/png")})
    assert response.status_code == 200
    assert client.get("/api/settings").json()["has_logo"] is True
    assert client.get("/api/brand/logo").content == b"\x89PNG"
    assert client.post("/api/brand/logo", files={"file": ("logo.gif", b"GIF", "image/gif")}).status_code == 400
    client.delete("/api/brand/logo")
    assert client.get("/api/brand/logo").status_code == 404


def test_brand_defaults_merge(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch, brand={"primary_color": "#000000"})
    brand = settings.load()["brand"]
    assert brand["primary_color"] == "#000000" and brand["font"] == "Tajawal"


def test_render_extras_use_brand(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch, brand={"accent_color": "#112233", "font": "Cairo", "logo_position": "bottom-left"})
    (tmp_path / "brand").mkdir()
    (tmp_path / "brand" / "logo.png").write_bytes(b"png")
    from montage.timeline import normalize

    timeline = normalize({"aspect": "9:16", "duration": 10, "base": {"file": "a.wav"},
                          "cuts": [{"id": "a", "start": 0, "end": 1.5, "auto": "silence"}],
                          "captions": [{"id": "c", "start": 2, "end": 3, "text": "كلام"}],
                          "clips": [], "brand": {"logo": True, "title": True}})
    extras = pipeline.render_extras(timeline, tmp_path, {"name": "فلوسك حلال ولا حرام"})
    assert extras["logo"]["position"] == "bottom-left"
    ass = extras["subtitles"].read_text(encoding="utf-8")
    assert "Style: Title,Cairo" in ass and "&H10332211" in ass
    # العنوان بيبدأ بعد السكتة المقصوصة في الأول
    assert "Dialogue: 1,0:00:01.70,0:00:04.70,Title" in ass


def test_no_logo_when_turned_off(tmp_path, monkeypatch):
    _settings(tmp_path, monkeypatch)
    (tmp_path / "brand").mkdir()
    (tmp_path / "brand" / "logo.png").write_bytes(b"png")
    from montage.timeline import normalize

    timeline = normalize({"aspect": "16:9", "duration": 10, "base": {"file": "a.wav"}, "clips": [],
                          "brand": {"logo": False, "title": False}})
    extras = pipeline.render_extras(timeline, tmp_path, {"name": "x"})
    assert "logo" not in extras and "subtitles" not in extras
