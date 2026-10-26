from conftest import fake_transcript
from montage.aligner import align, to_dicts
from montage.script_parser import parse_script
from montage.timeline import build_timeline, kept_duration, merge_cuts


def test_clips_follow_paragraphs_without_overlap(example_script):
    script = parse_script(example_script).to_dict()
    words = fake_transcript(script["paragraphs"])
    duration = words[-1]["end"] + 1
    timings = to_dicts(align(script["paragraphs"], words, duration))
    timeline = build_timeline(script, timings, duration, {"file": "recording.wav", "has_video": False,
                                                          "volume": 1.0}, "9:16")
    clips = timeline["clips"]
    assert len(clips) == 17
    for a, b in zip(clips, clips[1:]):
        assert a["end"] <= b["start"] + 1e-6
    timing_map = {t["paragraph_id"]: t for t in timings}
    first_shot = script["shots"][0]
    assert clips[0]["start"] == round(timing_map[first_shot["paragraph_id"]]["start"], 3)
    assert all(c["end"] - c["start"] >= 0.5 for c in clips)
    assert all(c["end"] <= duration for c in clips)


def test_two_shots_share_a_paragraph():
    script = {"shots": [
        {"id": "a", "kind": "image", "description": "x", "paragraph_id": "p1"},
        {"id": "b", "kind": "video", "description": "y", "paragraph_id": "p1"}]}
    timings = [{"paragraph_id": "p1", "start": 10.0, "end": 20.0, "estimated": False}]
    clips = build_timeline(script, timings, 30.0, {}, "16:9")["clips"]
    assert clips[0]["start"] == 10.0 and clips[1]["start"] == 15.0
    assert clips[0]["end"] <= clips[1]["start"]
    assert clips[0]["motion"] == "zoom_in" and clips[1]["motion"] == "none"


def test_cuts_merge_and_duration():
    cuts = [{"start": 5, "end": 7}, {"start": 6, "end": 9}, {"start": 20, "end": 25}]
    assert merge_cuts(cuts, 22) == [(5, 9), (20, 22)]
    assert kept_duration(30, cuts) == 30 - 4 - 5


def _base():
    return {"file": "recording.wav", "has_video": False, "volume": 1.0}


def test_short_recording_skips_unspoken_shots_and_marks_estimates(example_script):
    script = parse_script(example_script).to_dict()
    spoken = script["paragraphs"][:12]
    words = fake_transcript(spoken)
    duration = words[-1]["end"] + 1
    timings = to_dicts(align(script["paragraphs"], words, duration))
    timeline = build_timeline(script, timings, duration, _base(), "9:16")
    assert 0 < len(timeline["clips"]) < 17
    assert all(c["start"] < duration for c in timeline["clips"])
    assert all(m["start"] < duration for m in timeline["markers"])
    estimated_paragraphs = {t["paragraph_id"] for t in timings if t["estimated"]}
    for clip in timeline["clips"]:
        shot = next(s for s in script["shots"] if s["id"] == clip["shot_id"])
        assert clip["estimated"] == (shot["paragraph_id"] in estimated_paragraphs)


def test_page_images_open_their_sections(example_script):
    script = parse_script(example_script).to_dict()
    words = fake_transcript(script["paragraphs"])
    duration = words[-1]["end"] + 1
    timings = to_dicts(align(script["paragraphs"], words, duration))
    pages = {1: {"file": "page_1.png", "kind": "image", "source": "page"},
             3: {"file": "page_3.jpg", "kind": "image", "source": "page"}}
    timeline = build_timeline(script, timings, duration, _base(), "9:16", pages=pages)
    page_clips = [c for c in timeline["clips"] if c["page"]]
    assert [c["page"] for c in page_clips] == [1, 3]
    assert all(c["fit"] == "contain" and c["media"]["file"].startswith("page_") for c in page_clips)
    clips = sorted(timeline["clips"], key=lambda c: c["start"])
    for a, b in zip(clips, clips[1:]):
        assert a["end"] <= b["start"] + 1e-6
    assert all(c["end"] - c["start"] >= 0.5 for c in clips)
    assert len(timeline["clips"]) == 17 + 2


def test_old_timeline_gets_new_defaults():
    from montage.timeline import normalize

    old = {"version": 1, "aspect": "9:16", "duration": 5, "base": {"file": "a.wav", "volume": 1},
           "cuts": [], "clips": [{"id": "c", "start": 0, "end": 1}], "markers": []}
    new = normalize(old)
    assert new["version"] == 2 and new["captions"] == [] and "music" not in new
    assert new["base"]["clean_audio"] is True
    assert new["caption_style"]["font"] == "Tajawal"
    assert new["clips"][0]["fit"] == "cover" and new["clips"][0]["estimated"] is False
