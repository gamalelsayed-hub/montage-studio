"""تحديث تلقائي بعد ما ينزّل نسخة جديدة (ZIP فوق القديمة):

- لو ملفات الواجهة اتغيّرت عن آخر مرة اتبنت ← npm install + npm run build.
- لو requirements.txt اتغيّر ← pip install.

المقارنة بالمحتوى (hash) مش بتاريخ الملفات، لأن ملفات الـ ZIP تاريخها تاريخ النسخة على GitHub.
start.bat وsetup.bat والبرنامج نفسه بيشغّلوا الملف ده، فصاحب المشروع مش محتاج يعمل حاجة بإيده.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from .media import _NO_WINDOW
from .settings import ROOT

log = logging.getLogger(__name__)

FRONTEND = ROOT / "frontend"
BUILD_MARK = FRONTEND / "dist" / ".build-hash"
REQUIREMENTS = ROOT / "backend" / "requirements.txt"
REQUIREMENTS_MARK = Path(sys.prefix) / ".requirements-hash"


def _hash_files(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for file in sorted(files):
        digest.update(file.relative_to(ROOT).as_posix().encode())
        digest.update(file.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:16]


def frontend_hash() -> str:
    files = [p for folder in ("src", "public") for p in (FRONTEND / folder).rglob("*") if p.is_file()]
    files += [FRONTEND / name for name in ("index.html", "package.json", "vite.config.ts", "tsconfig.json")
              if (FRONTEND / name).exists()]
    return _hash_files(files)


def _say(message: str) -> None:
    log.info(message)
    try:
        print(message, flush=True)
    except Exception:  # pythonw مالوش شاشة
        pass


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _run(args: list[str], cwd: Path) -> bool:
    _say("  > " + " ".join(args))
    result = subprocess.run(args, cwd=cwd, creationflags=_NO_WINDOW)
    return result.returncode == 0


def ensure_python_packages() -> None:
    wanted = _hash_files([REQUIREMENTS])
    if _read(REQUIREMENTS_MARK) == wanted:
        return
    _say("بنزّل مكتبات Python الجديدة…")
    if _run([sys.executable, "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS)], ROOT):
        try:
            REQUIREMENTS_MARK.write_text(wanted, encoding="utf-8")
        except OSError:
            pass
    else:
        log.warning("pip install failed; continuing with the installed packages")


def ensure_frontend() -> None:
    wanted = frontend_hash()
    if (FRONTEND / "dist" / "index.html").exists() and _read(BUILD_MARK) == wanted:
        return
    npm = shutil.which("npm")
    if not npm:
        log.warning("npm not found; the interface was not rebuilt")
        return
    _say("بنحدّث الواجهة (نص دقيقة تقريبًا)…")
    if _run([npm, "install", "--no-audit", "--no-fund"], FRONTEND) and _run([npm, "run", "build"], FRONTEND):
        BUILD_MARK.write_text(wanted, encoding="utf-8")
    else:
        log.warning("building the interface failed; using the old one if it exists")


def ensure_up_to_date() -> None:
    ensure_python_packages()
    ensure_frontend()


if __name__ == "__main__":
    ensure_up_to_date()
    if not (FRONTEND / "dist" / "index.html").exists():
        sys.exit(1)
