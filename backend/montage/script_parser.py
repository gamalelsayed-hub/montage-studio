"""قراءة السكريبت (Markdown) وتحويله لأقسام وفقرات منطوقة ولقطات وملاحظات.

الشكل متشرح في CLAUDE.md:
- `## عنوان` = قسم، و`## صفحة N` بيحفظ رقم الصفحة.
- `**[صورة]** وصف` و`**[فيديو]** وصف` = لقطة، تتربط بالفقرة اللي بعدها (ولو مافيش، باللي قبلها).
- `**[ملحوظة]** …` = ملاحظة للمونتاج.
- `[…]` لوحدها في السطر = تعليمة للمتكلم.
- أي فقرة تانية (أو بند في قايمة) = كلام منطوق.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_SHOT = re.compile(r"^\*{0,2}\[(صوره|صورة|فيديو)\]\*{0,2}\s*[:：\-–]?\s*(.+)$")
_NOTE = re.compile(r"^\*{0,2}\[(ملحوظه|ملحوظة|ملاحظة|ملاحظه)\]\*{0,2}\s*[:：\-–]?\s*(.*)$")
_CUE = re.compile(r"^\[([^\]]+)\]$")
_PAGE = re.compile(r"صفح[ةه]\s*([0-9٠-٩]+)")
_LIST = re.compile(r"^(\s*[-*•]\s+|\s*\d+[.)]\s+)")


@dataclass
class Section:
    id: str
    title: str
    page: int | None
    level: int


@dataclass
class Paragraph:
    id: str
    section_id: str
    text: str


@dataclass
class Shot:
    id: str
    section_id: str
    kind: str  # "image" | "video"
    description: str
    paragraph_id: str | None = None


@dataclass
class Cue:
    id: str
    section_id: str
    kind: str  # "speaker" (للمتكلم) | "note" (للمونتاج)
    text: str
    paragraph_id: str | None = None


@dataclass
class Script:
    title: str
    sections: list[Section] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)
    cues: list[Cue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _clean_inline(text: str) -> str:
    """يشيل علامات Markdown من الكلام المنطوق."""
    text = re.sub(r"^>\s*", "", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # روابط
    return " ".join(text.split())


def parse_script(markdown: str) -> Script:
    script = Script(title="")
    section = Section(id="s0", title="", page=None, level=2)
    section_used = False
    pending_shots: list[Shot] = []  # لقطات مستنية أول فقرة بعدها
    pending_cues: list[Cue] = []
    para_buffer: list[str] = []
    counters = {"p": 0, "shot": 0, "cue": 0, "s": 0}

    def next_id(prefix: str) -> str:
        counters[prefix] += 1
        return f"{prefix}{counters[prefix]}"

    def ensure_section() -> None:
        nonlocal section_used
        if not section_used:
            script.sections.append(section)
            section_used = True

    def flush_paragraph() -> None:
        if not para_buffer:
            return
        text = _clean_inline(" ".join(para_buffer))
        para_buffer.clear()
        if not text:
            return
        ensure_section()
        para = Paragraph(id=next_id("p"), section_id=section.id, text=text)
        script.paragraphs.append(para)
        for item in pending_shots + pending_cues:
            item.paragraph_id = para.id
        pending_shots.clear()
        pending_cues.clear()

    def attach_leftovers_to_previous() -> None:
        """اللقطات اللي مالقتش فقرة بعدها في نفس القسم تتربط باللي قبلها."""
        prev = next((p for p in reversed(script.paragraphs) if p.section_id == section.id), None)
        if prev is None:
            prev = script.paragraphs[-1] if script.paragraphs else None
        for item in pending_shots + pending_cues:
            item.paragraph_id = prev.id if prev else None
        pending_shots.clear()
        pending_cues.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line or line in ("---", "***"):
            flush_paragraph()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            title = _clean_inline(heading.group(2))
            if level == 1 and not script.title:
                script.title = title
                continue
            attach_leftovers_to_previous()
            page_match = _PAGE.search(title)
            page = int(page_match.group(1).translate(_ARABIC_DIGITS)) if page_match else None
            section = Section(id=next_id("s"), title=title, page=page, level=level)
            section_used = False
            ensure_section()
            continue

        shot = _SHOT.match(line)
        if shot:
            flush_paragraph()
            ensure_section()
            kind = "video" if shot.group(1) == "فيديو" else "image"
            item = Shot(id=next_id("shot"), section_id=section.id, kind=kind,
                        description=_clean_inline(shot.group(2)))
            script.shots.append(item)
            pending_shots.append(item)
            continue

        note = _NOTE.match(line)
        if note:
            flush_paragraph()
            ensure_section()
            item = Cue(id=next_id("cue"), section_id=section.id, kind="note",
                       text=_clean_inline(note.group(2)))
            script.cues.append(item)
            pending_cues.append(item)
            continue

        cue = _CUE.match(line)
        if cue:
            flush_paragraph()
            ensure_section()
            item = Cue(id=next_id("cue"), section_id=section.id, kind="speaker",
                       text=_clean_inline(cue.group(1)))
            script.cues.append(item)
            pending_cues.append(item)
            continue

        if line.startswith("|"):
            # الجداول شرح، مش كلام بيتقال
            continue

        if _LIST.match(raw):
            # كل بند في القايمة فقرة منطوقة لوحده
            flush_paragraph()
            para_buffer.append(_LIST.sub("", raw))
            flush_paragraph()
            continue

        para_buffer.append(line)

    flush_paragraph()
    attach_leftovers_to_previous()
    return script
