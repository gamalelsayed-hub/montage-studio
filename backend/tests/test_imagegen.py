import base64

import httpx
import pytest

from montage import imagegen


class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data = status, data

    def json(self):
        return self._data


PNG = base64.b64encode(b"\x89PNG fake").decode()


def test_generate_saves_image_and_sends_content_rule(tmp_path, monkeypatch):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append(json)
        return FakeResponse(200, {"data": [{"b64_json": PNG}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    media = imagegen.generate("ست بتشتري من السوق", "9:16", {"openai_api_key": "k", "openai_image_model": "gpt-image-1-mini"},
                              tmp_path)
    assert (tmp_path / media["file"]).read_bytes() == b"\x89PNG fake"
    assert media["source"] == "ai" and media["kind"] == "image"
    assert calls[0]["size"] == "1024x1536" and calls[0]["model"] == "gpt-image-1-mini"
    assert "hijab" in calls[0]["prompt"] and "ست بتشتري من السوق" in calls[0]["prompt"]


def test_falls_back_when_model_missing(tmp_path, monkeypatch):
    responses = [FakeResponse(404, {"error": {"code": "model_not_found", "message": "no"}}),
                 FakeResponse(200, {"data": [{"b64_json": PNG}]})]
    models = []

    def fake_post(url, json, headers, timeout):
        models.append(json["model"])
        return responses.pop(0)

    monkeypatch.setattr(httpx, "post", fake_post)
    media = imagegen.generate("x", "16:9", {"openai_api_key": "k", "openai_image_model": "gpt-image-1-mini"}, tmp_path)
    assert models == ["gpt-image-1-mini", "gpt-image-1"]
    assert media["author"] == "gpt-image-1"


@pytest.mark.parametrize("status,error,expected", [
    (401, {}, "غلط"),
    (400, {"code": "moderation_blocked", "message": "blocked"}, "رفض"),
    (429, {"code": "insufficient_quota", "message": "quota"}, "رصيد"),
    (403, {"message": "Your organization must be verified"}, "توثيق"),
])
def test_errors_in_arabic(tmp_path, monkeypatch, status, error, expected):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(status, {"error": error}))
    with pytest.raises(imagegen.ImageGenError, match=expected):
        imagegen.generate("x", "9:16", {"openai_api_key": "k"}, tmp_path)


def test_needs_key(tmp_path):
    with pytest.raises(imagegen.ImageGenError, match="مفتاح"):
        imagegen.generate("x", "9:16", {}, tmp_path)
