import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run  # noqa: E402


def test_find_browser_prefers_first_existing(tmp_path, monkeypatch):
    edge = tmp_path / "msedge.exe"
    edge.write_text("")
    monkeypatch.setattr(run, "BROWSERS", [str(tmp_path / "missing.exe"), str(edge)])
    assert run.find_browser() == str(edge)


def test_no_browser(monkeypatch):
    monkeypatch.setattr(run, "BROWSERS", [r"C:\nope\x.exe"])
    assert run.find_browser() is None


def test_server_not_running_on_free_port(monkeypatch):
    monkeypatch.setattr(run, "URL", "http://127.0.0.1:9")
    assert run.server_running() is False
