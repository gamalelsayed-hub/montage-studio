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
