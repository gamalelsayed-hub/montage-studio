import json

import httpx

from montage import keywords


class FakeResponse:
    def __init__(self, status, data=None):
        self.status_code, self._data = status, data or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


def gemini_answer(queries):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps({"queries": queries})}]}}]}


def test_gemini_writes_queries_and_skips_missing_models(monkeypatch):
    calls = []

    def fake_post(url, json, timeout, headers):
        calls.append(url)
        if len(calls) == 1:
            return FakeResponse(404)
        assert headers["x-goog-api-key"] == "AIza-test"
        assert "hijab" in json["contents"][0]["parts"][0]["text"]  # قواعد المحتوى بتتبعت
        return FakeResponse(200, gemini_answer(["old souk wheat sack", "woman shopping market"]))

    monkeypatch.setattr(httpx, "post", fake_post)
    queries, source = keywords.make_queries(["سوق قديم", "ست بتشتري"], gemini_api_key="AIza-test")
    assert source == "gemini"
    assert queries[0] == "old souk wheat sack"
    assert "hijab" in queries[1]
    assert keywords.GEMINI_MODELS[1] in calls[1]


def test_gemini_failure_falls_back_to_dictionary(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(400))
    queries, source = keywords.make_queries(["دهب"], gemini_api_key="bad")
    assert source == "dictionary" and "gold" in queries[0]


def test_claude_is_tried_before_gemini(monkeypatch):
    monkeypatch.setattr(keywords, "_claude_queries", lambda d, k: ["from claude"])
    monkeypatch.setattr(keywords, "_gemini_queries", lambda d, k: ["from gemini"])
    assert keywords.make_queries(["x"], "sk-ant", "AIza")[1] == "claude"
