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
