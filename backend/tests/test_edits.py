from montage.edits import auto_cuts, retake_cuts, silence_cuts


def _words(items):
    return [{"word": w, "start": s, "end": e} for w, s, e in items]


def test_long_silences_are_cut_with_padding():
    words = _words([("قبل", 1.0, 1.3), ("ما", 1.4, 1.6), ("نتكلم", 3.0, 3.5)])
    cuts = silence_cuts(words, duration=6.0)
    # أول التسجيل، والسكتة 1.6 ← 3.0، وآخر التسجيل
    assert cuts == [
        {"start": 0.0, "end": 0.8, "auto": "silence"},
        {"start": 1.8, "end": 2.8, "auto": "silence"},
        {"start": 3.7, "end": 6.0, "auto": "silence"},
    ]


def test_short_pauses_stay():
    words = _words([("ا", 0.1, 0.5), ("ب", 0.9, 1.2)])
    assert silence_cuts(words, duration=1.3) == []


def test_repeated_start_cuts_first_attempt():
    words = _words([("الفلوس", 1.0, 1.4), ("دي", 1.5, 1.7), ("جت", 1.8, 2.0),
                    ("الفلوس", 2.6, 3.0), ("دي", 3.1, 3.3), ("جت", 3.4, 3.6), ("منين", 3.7, 4.0)])
    assert retake_cuts(words) == [{"start": 0.9, "end": 2.5, "auto": "retake"}]


def test_normal_speech_has_no_retakes():
    words = _words([(w, i, i + 0.3) for i, w in enumerate("قبل ما نتكلم عن الربا لازم نفهم".split())])
    assert retake_cuts(words) == []


def test_auto_cuts_have_ids_and_order():
    words = _words([("ا", 2.0, 2.3), ("ب", 2.4, 2.6), ("ا", 2.9, 3.1), ("ب", 3.2, 3.4)])
    cuts = auto_cuts(words, duration=5.0)
    assert [c["id"] for c in cuts] == ["auto1", "auto2", "auto3"]
    assert [c["auto"] for c in cuts] == ["silence", "retake", "silence"]
