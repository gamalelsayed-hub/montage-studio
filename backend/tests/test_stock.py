import httpx
import pytest

from montage import pexels, pixabay, stock


class FakeResponse:
    def __init__(self, data, status=200, text=""):
        self._data, self.status_code, self.text = data, status, text

    def json(self):
        return self._data


PHOTO_HITS = {"hits": [{"id": 1, "pageURL": "https://pixabay.com/p/1", "previewURL": "s.jpg",
                        "webformatURL": "m.jpg", "largeImageURL": "l.jpg", "imageWidth": 1280,
                        "imageHeight": 1920, "user": "ahmed"}]}
VIDEO_HITS = {"hits": [
    {"id": 7, "pageURL": "p7", "duration": 12, "user": "u", "videos": {
        "large": {"url": "", "width": 0, "height": 0},
        "medium": {"url": "m7.mp4", "width": 1920, "height": 1080, "thumbnail": "t7.jpg"},
        "small": {"url": "s7.mp4", "width": 1280, "height": 720, "thumbnail": "t7s.jpg"}}},
    {"id": 8, "pageURL": "p8", "duration": 9, "user": "u", "videos": {
        "medium": {"url": "m8.mp4", "width": 1080, "height": 1920, "thumbnail": "t8.jpg"}}},
]}


def test_pixabay_photos(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params))
        return FakeResponse(PHOTO_HITS)

    monkeypatch.setattr(httpx, "get", fake_get)
    results = pixabay.search("woman market hijab", "image", "k", "9:16")
    assert results == [{"source": "pixabay", "kind": "image", "id": "1", "thumb": "m.jpg", "url": "l.jpg",
                        "width": 1280, "height": 1920, "author": "ahmed", "page": "https://pixabay.com/p/1"}]
    url, params = calls[0]
    assert url == pixabay.API and params["orientation"] == "vertical" and params["safesearch"] == "true"


def test_pixabay_videos_pick_full_hd_and_portrait_first(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, params, timeout: FakeResponse(VIDEO_HITS))
    results = pixabay.search("gold vault", "video", "k", "9:16")
    assert [r["id"] for r in results] == ["8", "7"]  # الطولي الأول
    landscape = next(r for r in results if r["id"] == "7")
    assert landscape["url"] == "m7.mp4" and landscape["thumb"] == "t7.jpg" and landscape["duration"] == 12


def test_pixabay_bad_key(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda url, params, timeout:
                        FakeResponse({}, 400, "[ERROR 400] Invalid or missing API key"))
    with pytest.raises(stock.StockError, match="غلط"):
        pixabay.search("x", "image", "bad")


def test_stock_prefers_pixabay_and_falls_back(monkeypatch):
    monkeypatch.setattr(pixabay, "search", lambda *a: [])
    monkeypatch.setattr(pexels, "search", lambda *a: [{"id": "p"}])
    config = {"pixabay_api_key": "a", "pexels_api_key": "b"}
    assert stock.search("q", "image", config) == [{"id": "p"}]
    assert [name for name, _ in stock.providers(config)] == ["pixabay", "pexels"]


def test_stock_without_keys():
    assert not stock.has_key({"pixabay_api_key": "", "pexels_api_key": ""})
    with pytest.raises(stock.StockError, match="Pixabay"):
        stock.search("q", "image", {})
