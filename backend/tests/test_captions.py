from montage.captions import _ass_color, build_captions, write_ass


def _words(text, start=0.0, step=0.4):
    return [{"word": w, "start": round(start + i * step, 3), "end": round(start + i * step + 0.3, 3)}
            for i, w in enumerate(text.split())]


def test_lines_break_by_length_and_pause():
    words = _words("قبل ما نتكلم عن الربا لازم نفهم الجنيه اللي في جيبك") + _words("ده جه منين", start=10)
    caps = build_captions(words, max_words=6)
    assert [c["text"] for c in caps] == ["قبل ما نتكلم عن الربا لازم", "نفهم الجنيه اللي في جيبك", "ده جه منين"]
    assert caps[0]["start"] == 0.0
    # السطر بيفضل لحد ما اللي بعده يبدأ لو المسافة صغيرة
    assert caps[0]["end"] == caps[1]["start"]
    assert caps[2]["start"] == 10.0


def test_sentence_end_closes_line():
    caps = build_captions(_words("فلوسك حلال ولا حرام؟ تعالى نشوف"))
    assert caps[0]["text"] == "فلوسك حلال ولا حرام؟"


def test_ass_file(tmp_path):
    caps = [{"id": "c1", "start": 1.0, "end": 2.5, "text": "فلوسك {حلال}"}]
    path = write_ass(tmp_path / "c.ass", caps, {"font": "Cairo", "color": "#FFCC00"}, 1080, 1920,
                     title={"text": "العنوان", "start": 0.2, "end": 3.2})
    text = path.read_text(encoding="utf-8")
    assert "PlayResY: 1920" in text
    assert "Style: Caption,Cairo,64,&H0000CCFF" in text
    assert "Dialogue: 0,0:00:01.00,0:00:02.50,Caption,,0,0,0,,فلوسك (حلال)" in text
    assert "Title" in text and "العنوان" in text


def test_disabled_captions_keep_only_title(tmp_path):
    caps = [{"id": "c1", "start": 1.0, "end": 2.5, "text": "كلام"}]
    text = write_ass(tmp_path / "c.ass", caps, {"enabled": False}, 1080, 1920).read_text(encoding="utf-8")
    assert "كلام" not in text


def test_ass_color():
    assert _ass_color("#13202E") == "&H002E2013"
    assert _ass_color("bad") == "&H00FFFFFF"
