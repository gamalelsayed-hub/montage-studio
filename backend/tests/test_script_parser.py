from montage.script_parser import parse_script


def test_example_script_structure(example_script):
    script = parse_script(example_script)
    assert script.title == "سكريبت فيديو: فلوسك حلال ولا حرام؟"
    assert len(script.shots) == 17
    assert sum(1 for s in script.shots if s.kind == "video") == 4
    pages = [s.page for s in script.sections if s.page]
    assert pages == [1, 2, 3, 4, 5, 6, 7]
    # كل لقطة مربوطة بفقرة
    assert all(s.paragraph_id for s in script.shots)


def test_shot_links_to_next_paragraph():
    md = """## صفحة ١: تجربة

كلام قبل اللقطة.

**[صورة]** سوق قديم

[زووم على الخطوة ١]

الكلام اللي بعد اللقطة.
"""
    script = parse_script(md)
    shot = script.shots[0]
    para = next(p for p in script.paragraphs if p.id == shot.paragraph_id)
    assert para.text == "الكلام اللي بعد اللقطة."
    assert script.sections[0].page == 1
    cue = script.cues[0]
    assert cue.kind == "speaker" and cue.text == "زووم على الخطوة ١"


def test_shot_at_end_of_section_links_to_previous():
    md = """## قسم ١

آخر كلام في القسم.

**[فيديو]** خزنة بنك

## قسم ٢

كلام القسم التاني.
"""
    script = parse_script(md)
    shot = script.shots[0]
    para = next(p for p in script.paragraphs if p.id == shot.paragraph_id)
    assert para.text == "آخر كلام في القسم."
    assert shot.kind == "video"


def test_note_and_cue_are_not_shots():
    md = """## قسم

**[ملحوظة]** خليك على اللوحة

[اشاور على الفهرس]

**السؤال الأول:** السعر ثابت؟
"""
    script = parse_script(md)
    assert script.shots == []
    assert [c.kind for c in script.cues] == ["note", "speaker"]
    assert script.paragraphs[0].text == "السؤال الأول: السعر ثابت؟"


def test_list_items_are_spoken_paragraphs():
    md = """## صفحة ٦

دي البدايل:

1. **قسّط من البياع نفسه.** كلام.
2. **الجمعية.** كلام تاني.
"""
    script = parse_script(md)
    assert [p.text for p in script.paragraphs] == [
        "دي البدايل:", "قسّط من البياع نفسه. كلام.", "الجمعية. كلام تاني."]
