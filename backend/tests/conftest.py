import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

EXAMPLE = Path(__file__).resolve().parents[2] / "docs" / "script-example.md"


@pytest.fixture
def example_script() -> str:
    return EXAMPLE.read_text(encoding="utf-8")


def fake_transcript(paragraphs, words_per_second=2.5, skip=(), start=1.0):
    """تفريغ مزيف: كل كلمة من الفقرات بتوقيت ثابت، مع إمكانية تخطي فقرات."""
    words, t = [], start
    for para in paragraphs:
        if para["id"] in skip:
            continue
        for word in para["text"].split():
            words.append({"word": word, "start": round(t, 3), "end": round(t + 0.35, 3)})
            t += 1 / words_per_second
        t += 0.8  # سكتة بين الفقرات
    return words
