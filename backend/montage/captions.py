"""الترجمة على الشاشة (عربي): سطور قصيرة من التفريغ، وملف ASS للتصدير.

السطر بيتقفل لما يوصل لعدد كلمات معيّن، أو عند سكتة، أو عند آخر الجملة.
الأوقات بتوقيت التسجيل الأصلي زي باقي التايم لاين.
"""

from __future__ import annotations

from pathlib import Path

from .settings import ROOT

FONTS_DIR = ROOT / "assets" / "fonts"
FONTS = ("Tajawal", "Cairo")  # الخطوط اللي جاية مع البرنامج في assets/fonts
MAX_WORDS = 6
MAX_SECONDS = 3.5
BREAK_GAP = 0.5

DEFAULT_STYLE = {
    "enabled": True,
    "font": "Tajawal",
    "size": 64,           # بالنسبة لعرض 1080
    "color": "#FFFFFF",
    "box": True,
    "box_color": "#13202E",
    "position": "bottom",  # bottom | middle | top
}


def build_captions(words: list[dict], max_words: int = MAX_WORDS) -> list[dict]:
    captions: list[dict] = []
    line: list[dict] = []

    def close() -> None:
        if line:
            captions.append({
                "id": f"cap{len(captions) + 1}",
                "start": round(float(line[0]["start"]), 3),
                "end": round(float(line[-1]["end"]), 3),
                "text": " ".join(w["word"].strip() for w in line),
            })
            line.clear()

    for word in words:
        if line:
            gap = float(word["start"]) - float(line[-1]["end"])
            too_long = float(word["end"]) - float(line[0]["start"]) > MAX_SECONDS
            if gap > BREAK_GAP or len(line) >= max_words or too_long:
                close()
        line.append(word)
        if word["word"].strip().endswith((".", "؟", "?", "!", "،", ":")) and len(line) >= 3:
            close()
    close()
    # السطر يفضل ظاهر لحد ما اللي بعده يبدأ (لو المسافة صغيرة)، عشان مايرمشش
    for current, following in zip(captions, captions[1:]):
        if following["start"] - current["end"] < 0.4:
            current["end"] = following["start"]
    return captions


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    """#RRGGBB ← &HAABBGGRR (ترتيب ASS بالعكس)."""
    value = (hex_color or "#FFFFFF").lstrip("#")
    if len(value) != 6:
        value = "FFFFFF"
    r, g, b = value[0:2], value[2:4], value[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ass_time(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ass_text(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def write_ass(path: Path, captions: list[dict], style: dict, width: int, height: int,
              title: dict | None = None) -> Path:
    """title (اختياري): {"text", "start", "end", "color", "font"} عنوان في أول الفيديو بهويته."""
    style = {**DEFAULT_STYLE, **(style or {})}
    scale = width / 1080
    size = int(round(float(style["size"]) * scale))
    alignment = {"bottom": 2, "middle": 5, "top": 8}.get(style["position"], 2)
    margin_v = int(round((height * 0.16) if style["position"] == "bottom" else (height * 0.1)))
    primary = _ass_color(style["color"])
    if style.get("box"):
        # BorderStyle 3 = مربع ورا الكلام، ولونه من OutlineColour
        border, outline_color, outline = 3, _ass_color(style["box_color"], 0x30), max(int(size * 0.25), 6)
    else:
        border, outline_color, outline = 1, _ass_color("#000000"), max(int(size * 0.07), 2)
    font = style["font"] if style["font"] in FONTS else DEFAULT_STYLE["font"]

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,{font},{size},{primary},{primary},{outline_color},&H80000000,-1,0,0,0,100,100,0,0,"
        f"{border},{outline},0,{alignment},{int(width * 0.08)},{int(width * 0.08)},{margin_v},1",
    ]
    if title:
        title_size = int(round(size * 1.35))
        title_font = title.get("font") if title.get("font") in FONTS else font
        lines.append(
            f"Style: Title,{title_font},{title_size},{_ass_color(title.get('color') or '#FFFFFF')},&H00FFFFFF,"
            f"{_ass_color(title.get('box_color') or '#13202E', 0x10)},&H80000000,-1,0,0,0,100,100,0,0,3,"
            f"{max(int(title_size * 0.35), 8)},0,5,{int(width * 0.08)},{int(width * 0.08)},0,1")
    lines += ["", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    if title and title.get("text"):
        lines.append(f"Dialogue: 1,{_ass_time(title['start'])},{_ass_time(title['end'])},Title,,0,0,0,,"
                     f"{{\\fad(300,300)}}{_ass_text(title['text'])}")
    if style.get("enabled", True):
        for caption in captions:
            if caption["end"] > caption["start"] and caption["text"].strip():
                lines.append(f"Dialogue: 0,{_ass_time(caption['start'])},{_ass_time(caption['end'])},Caption,,0,0,0,,"
                             f"{_ass_text(caption['text'])}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
