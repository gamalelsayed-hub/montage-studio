from conftest import fake_transcript
from montage.aligner import align
from montage.script_parser import parse_script


def _paragraphs(example_script):
    script = parse_script(example_script).to_dict()
    # قسم «إزاي تستخدم السكريبت» مش بيتقال في التسجيل
    spoken_sections = {s["id"] for s in script["sections"] if "إزاي تستخدم" not in s["title"]}
    return [p for p in script["paragraphs"] if p["section_id"] in spoken_sections], script


def test_exact_transcript_matches_every_paragraph(example_script):
    paragraphs, _ = _paragraphs(example_script)
    words = fake_transcript(paragraphs)
    timings = align(paragraphs, words)
    assert all(not t.estimated for t in timings)
    starts = [t.start for t in timings]
    assert starts == sorted(starts)
    assert timings[0].start == words[0]["start"]


def test_unspoken_meta_section_is_estimated(example_script):
    script = parse_script(example_script).to_dict()
    spoken, _ = _paragraphs(example_script)
    words = fake_transcript(spoken)
    timings = align(script["paragraphs"], words)
    meta_ids = {p["id"] for p in script["paragraphs"]} - {p["id"] for p in spoken}
    for t in timings:
        if t.paragraph_id in meta_ids:
            assert t.estimated


def test_skipped_paragraph_gets_estimated_between_neighbours(example_script):
    paragraphs, _ = _paragraphs(example_script)
    skipped = paragraphs[10]["id"]
    words = fake_transcript(paragraphs, skip={skipped})
    timings = {t.paragraph_id: t for t in align(paragraphs, words)}
    prev_t, t, next_t = (timings[paragraphs[i]["id"]] for i in (9, 10, 11))
    assert t.estimated
    assert prev_t.end <= t.start <= t.end <= next_t.start


def test_spelling_differences_and_fillers_still_match():
    paragraphs = [
        {"id": "p1", "text": "قبل ما نتكلم عن الربا، لازم نفهم الجنيه اللي في جيبك ده جه منين."},
        {"id": "p2", "text": "فالناس اتفقت على الدهب والفضة: مابيبوظوش، وبيتقسموا، والكل بيقبلهم."},
    ]
    spoken = ("اممم قبل ما نتكلم على الربا لازم نفهم الجنية اللى فى جيبك دا جه منين "
              "يعني الناس اتفقت علي الذهب و الفضه ما بيبوظوش وبيتقسموا والكل بيقبلهم").split()
    words = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate(spoken)]
    timings = align(paragraphs, words)
    assert not timings[0].estimated and not timings[1].estimated
    assert timings[0].end < timings[1].start
    assert timings[1].start >= 0.4 * spoken.index("الناس") - 0.5


def test_retake_uses_one_take_and_keeps_order():
    paragraphs = [{"id": "p1", "text": "الجملة الأولى في الفيديو"},
                  {"id": "p2", "text": "والجملة التانية بعدها على طول"}]
    spoken = "الجملة الأولى في الفيديو الجملة الأولى في الفيديو والجملة التانية بعدها على طول".split()
    words = [{"word": w, "start": float(i), "end": i + 0.5} for i, w in enumerate(spoken)]
    timings = align(paragraphs, words)
    assert timings[0].start < timings[1].start
