"""تطبيع النص العربي عشان المطابقة بين السكريبت والتفريغ."""

import re

# التشكيل وعلامات القرآن
_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ALEF = re.compile(r"[أإآٱ]")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize(text: str) -> str:
    """يشيل التشكيل والتطويل والترقيم، ويوحّد الألف والياء والتاء المربوطة."""
    text = text.translate(_ARABIC_DIGITS)
    text = _DIACRITICS.sub("", text)
    text = text.replace(_TATWEEL, "")
    text = _ALEF.sub("ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.lower().split())


def tokens(text: str) -> list[str]:
    return normalize(text).split()
