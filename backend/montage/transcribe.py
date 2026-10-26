"""التفريغ المحلي بـ faster-whisper: كارت الشاشة الأول، ولو فشل يرجع للـ CPU."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

_model_cache: dict[tuple[str, str, str], object] = {}


def _add_cuda_dlls() -> None:
    """على ويندوز: مكتبات CUDA اللي setup.bat نزّلها (nvidia-cublas / nvidia-cudnn) لازم تبقى في الـ PATH."""
    if sys.platform != "win32":
        return
    for base in map(Path, sys.path):
        nvidia = base / "nvidia"
        if not nvidia.is_dir():
            continue
        for bin_dir in nvidia.glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


def _load_model(model_name: str, device: str):
    _add_cuda_dlls()
    from faster_whisper import WhisperModel

    attempts: list[tuple[str, str, str]] = []
    if device in ("auto", "cuda"):
        attempts.append((model_name, "cuda", "float16"))
    if device in ("auto", "cpu"):
        # على الـ CPU الموديل الكبير بطيء جدًا، فبنستخدم medium
        cpu_model = model_name if device == "cpu" else "medium"
        attempts.append((cpu_model, "cpu", "int8"))

    last_error: Exception | None = None
    for name, dev, compute in attempts:
        key = (name, dev, compute)
        if key in _model_cache:
            return _model_cache[key], dev
        try:
            model = WhisperModel(name, device=dev, compute_type=compute)
            _model_cache[key] = model
            return model, dev
        except Exception as exc:  # مثلًا CUDA مش متثبتة
            log.warning("Whisper on %s failed: %s", dev, exc)
            last_error = exc
    raise RuntimeError(f"مش قادر أشغّل Whisper: {last_error}")


def transcribe(audio_path: Path, model_name: str = "large-v3", device: str = "auto",
               hint_text: str = "", on_progress: Callable[[float], None] | None = None) -> dict:
    """بيرجع {"language", "duration", "device", "words": [{word, start, end}], "segments": [...]}."""
    model, used_device = _load_model(model_name, device)
    # أول جزء من السكريبت كتلميح بيساعد Whisper في الكلمات والأسلوب المصري
    prompt = hint_text[:600] if hint_text else None
    segments, info = model.transcribe(
        str(audio_path), language="ar", word_timestamps=True, vad_filter=True,
        initial_prompt=prompt, beam_size=5,
    )
    words: list[dict] = []
    out_segments: list[dict] = []
    for segment in segments:
        out_segments.append({"start": segment.start, "end": segment.end, "text": segment.text.strip()})
        for word in segment.words or []:
            text = word.word.strip()
            if text:
                words.append({"word": text, "start": round(word.start, 3), "end": round(word.end, 3),
                              "probability": round(word.probability, 3)})
        if on_progress and info.duration:
            on_progress(min(segment.end / info.duration, 1.0))
    return {"language": info.language, "duration": info.duration, "device": used_device,
            "words": words, "segments": out_segments}
