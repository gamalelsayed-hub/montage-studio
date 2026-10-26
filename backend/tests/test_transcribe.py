from montage import transcribe


class FakeModel:
    def __init__(self, name, device, compute_type):
        if device == "cuda":
            raise RuntimeError("no CUDA")
        self.name, self.device = name, device


def _patch(monkeypatch, has_cuda):
    import sys
    import types

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    monkeypatch.setattr(transcribe, "_has_cuda", lambda: has_cuda)
    monkeypatch.setattr(transcribe, "_model_cache", {})


def test_auto_without_nvidia_uses_turbo_on_cpu(monkeypatch):
    _patch(monkeypatch, has_cuda=False)
    model, device = transcribe._load_model("large-v3", "auto")
    assert device == "cpu" and model.name == "turbo"


def test_auto_with_broken_cuda_falls_back(monkeypatch):
    _patch(monkeypatch, has_cuda=True)
    model, device = transcribe._load_model("large-v3", "auto")
    assert device == "cpu" and model.name == "turbo"


def test_cpu_keeps_chosen_model(monkeypatch):
    _patch(monkeypatch, has_cuda=False)
    model, _ = transcribe._load_model("medium", "cpu")
    assert model.name == "medium"
