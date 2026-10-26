import json

from montage import settings


def test_moved_folder_falls_back_to_default(tmp_path, monkeypatch):
    file = tmp_path / "settings.local.json"
    file.write_text(json.dumps({"projects_dir": str(tmp_path / "moved-away" / "projects"),
                                "pixabay_api_key": "abc"}), encoding="utf-8")
    monkeypatch.setattr(settings, "SETTINGS_FILE", file)
    data = settings.load()
    assert data["projects_dir"] == settings.DEFAULTS["projects_dir"]
    assert data["pixabay_api_key"] == "abc"


def test_save_keeps_only_changed_values(tmp_path, monkeypatch):
    file = tmp_path / "settings.local.json"
    monkeypatch.setattr(settings, "SETTINGS_FILE", file)
    settings.save({"pixabay_api_key": "k", "projects_dir": settings.DEFAULTS["projects_dir"],
                   "whisper_model": "turbo"})
    assert json.loads(file.read_text(encoding="utf-8")) == {"pixabay_api_key": "k", "whisper_model": "turbo"}
    # المفتاح المخفي الراجع من الواجهة مايمسحش الحقيقي
    settings.save({"pixabay_api_key": "••••k"})
    assert settings.load()["pixabay_api_key"] == "k"
