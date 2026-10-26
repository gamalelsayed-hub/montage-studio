import shutil
import subprocess

import pytest

from montage.media import probe
from montage.render import build_command, render

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg مش متثبت")


def _timeline(has_video=False, file="recording.wav", aspect="9:16"):
    return {
        "version": 1, "aspect": aspect, "duration": 6.0,
        "base": {"file": file, "has_video": has_video, "volume": 0.8},
        "cuts": [{"id": "cut1", "start": 2.0, "end": 3.0}],
        "clips": [
            {"id": "c1", "kind": "image", "start": 0.5, "end": 2.5, "motion": "zoom_in", "volume": 0,
             "media": {"file": "pic.png", "kind": "image"}},
            {"id": "c2", "kind": "video", "start": 3.5, "end": 5.5, "motion": "none", "volume": 0,
             "media": {"file": "clip.mp4", "kind": "video"}},
            {"id": "c3", "kind": "image", "start": 5.5, "end": 6.0, "media": None},
        ],
    }


@needs_ffmpeg
def test_command_shape(tmp_path):
    args = build_command(_timeline(), tmp_path, tmp_path / "out.mp4")
    graph = args[args.index("-filter_complex") + 1]
    assert "color=c=0x13202E:s=1080x1920" in " ".join(args)
    assert "zoompan" in graph
    assert "between(t,0.5,2.5)" in graph and "between(t,3.5,5.5)" in graph
    assert "select='not(between(t,2,3))'" in graph
    assert "aselect='not(between(t,2,3))'" in graph
    assert "[1:a]volume=0.8" in graph
    # اللقطة اللي مالهاش ملف ماتدخلش
    assert args.count("-i") == 4
    assert args[args.index("-t", args.index("-filter_complex")) + 1] == "5"


@needs_ffmpeg
def test_landscape_video_base(tmp_path):
    args = build_command(_timeline(True, "recording.mp4", "16:9"), tmp_path, tmp_path / "o.mp4")
    graph = args[args.index("-filter_complex") + 1]
    assert graph.startswith("[0:v]scale=1920:1080")
    assert "[0:a]volume" in graph


def _make_inputs(path, base_video):
    ff = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if base_video:
        subprocess.run(ff + ["-f", "lavfi", "-i", "testsrc=s=640x360:r=25:d=6", "-f", "lavfi",
                             "-i", "sine=f=300:d=6", "-shortest", "-c:v", "libx264", "-c:a", "aac",
                             str(path / "recording.mp4")], check=True)
    else:
        subprocess.run(ff + ["-f", "lavfi", "-i", "sine=f=440:d=6", str(path / "recording.wav")], check=True)
    (path / "media").mkdir()
    subprocess.run(ff + ["-f", "lavfi", "-i", "testsrc2=s=800x600", "-frames:v", "1",
                         str(path / "media" / "pic.png")], check=True)
    subprocess.run(ff + ["-f", "lavfi", "-i", "testsrc=s=1280x720:r=30:d=1", "-c:v", "libx264",
                         str(path / "media" / "clip.mp4")], check=True)


@needs_ffmpeg
@pytest.mark.parametrize("base_video", [False, True])
def test_real_render(tmp_path, base_video):
    _make_inputs(tmp_path, base_video)
    timeline = _timeline(base_video, "recording.mp4" if base_video else "recording.wav")
    progress = []
    out = render(timeline, tmp_path, tmp_path / "out.mp4", on_progress=progress.append)
    info = probe(out)
    assert info["has_video"] and info["has_audio"]
    assert (info["width"], info["height"]) == (1080, 1920)
    assert abs(info["duration"] - 5.0) < 0.3
    assert progress


@needs_ffmpeg
def test_encoder_options(tmp_path):
    for encoder, expected in (("h264_qsv", "nv12"), ("h264_nvenc", "yuv420p"), ("libx264", "yuv420p")):
        args = build_command(_timeline(), tmp_path, tmp_path / "o.mp4", encoder)
        assert args[args.index("-c:v") + 1] == encoder
        assert args[args.index("-pix_fmt") + 1] == expected


@needs_ffmpeg
def test_falls_back_to_cpu_encoder(tmp_path, monkeypatch):
    import montage.render as render_module

    _make_inputs(tmp_path, False)
    monkeypatch.setattr(render_module, "hardware_encoders", lambda: ["h264_qsv"])  # مافيش كارت في بيئة الاختبار
    out = render(_timeline(), tmp_path, tmp_path / "out.mp4")
    assert probe(out)["has_video"]


def _v2_inputs(tmp_path):
    _make_inputs(tmp_path, False)
    ff = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    subprocess.run(ff + ["-f", "lavfi", "-i", "color=c=red:s=300x120", "-frames:v", "1",
                         str(tmp_path / "logo.png")], check=True)
    timeline = _timeline()
    timeline["base"]["clean_audio"] = True
    timeline["clips"][0]["fit"] = "contain"
    return timeline


@needs_ffmpeg
def test_v2_command_parts(tmp_path):
    timeline = _v2_inputs(tmp_path)
    (tmp_path / "c.ass").write_text("[Script Info]\n", encoding="utf-8")
    args = build_command(timeline, tmp_path, tmp_path / "o.mp4", subtitles=tmp_path / "c.ass",
                         fonts_dir=tmp_path, logo={"file": tmp_path / "logo.png"})
    graph = args[args.index("-filter_complex") + 1]
    assert "afftdn" in graph and "loudnorm=I=-16" in graph
    assert "boxblur" in graph and "force_original_aspect_ratio=decrease" in graph
    assert "ass='" in graph and ":shaping=complex" in graph
    assert "sidechaincompress" not in graph  # مافيش موسيقى
    assert "overlay=W-w-43:43" in graph


@needs_ffmpeg
def test_v2_real_render_with_captions(tmp_path):
    from montage.captions import FONTS_DIR, write_ass

    timeline = _v2_inputs(tmp_path)
    ass = write_ass(tmp_path / "captions.ass", [{"id": "c", "start": 0.2, "end": 4.0, "text": "فلوسك حلال ولا حرام؟"}],
                    {}, 1080, 1920)
    out = render(timeline, tmp_path, tmp_path / "out.mp4", subtitles=ass, fonts_dir=FONTS_DIR,
                 logo={"file": tmp_path / "logo.png", "position": "bottom-left"})
    info = probe(out)
    assert info["has_video"] and info["has_audio"]
    assert abs(info["duration"] - 5.0) < 0.3
