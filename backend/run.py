"""تشغيل البرنامج.

- `python run.py` (من start.bat): السيرفر في الشباك الأسود، والواجهة في المتصفح.
- `pythonw run.py --app` (من أيقونة سطح المكتب): برنامج في شباك لوحده من غير شباك أسود.
  الشباك هو Edge (أو Chrome) في وضع «تطبيق» بملف خاص بالبرنامج، ولما يتقفل السيرفر بيقفل
  (بعد ما أي تصدير شغال يخلص).
"""

import logging
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

HOST, PORT = "127.0.0.1", 8765
URL = f"http://{HOST}:{PORT}"
ROOT = Path(__file__).resolve().parents[1]

BROWSERS = [
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
]


def server_running() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/settings", timeout=1):
            return True
    except Exception:
        return False


def find_browser() -> str | None:
    for candidate in BROWSERS:
        path = os.path.expandvars(candidate)
        if os.path.exists(path):
            return path
    return None


def open_window() -> subprocess.Popen | None:
    """شباك البرنامج. بيرجع العملية عشان نعرف إمتى يتقفل (أو None لو فتحناه في المتصفح العادي)."""
    browser = find_browser()
    if not browser:
        webbrowser.open(URL)
        return None
    profile = ROOT / ".edge-profile"  # ملف خاص بالبرنامج، فالشباك بيعيش لوحده عن المتصفح العادي
    return subprocess.Popen([browser, f"--app={URL}", f"--user-data-dir={profile}", "--no-first-run",
                             "--no-default-browser-check", "--start-maximized"])


def setup_logging(to_file: bool) -> None:
    handlers: list[logging.Handler] = []
    if to_file:
        (ROOT / "logs").mkdir(exist_ok=True)
        log_file = open(ROOT / "logs" / "app.log", "a", encoding="utf-8", buffering=1)
        # pythonw مالوش شاشة: أي print أو خطأ يروح للملف بدل ما يوقع البرنامج
        sys.stdout = sys.stderr = log_file
        handlers.append(logging.StreamHandler(log_file))
    else:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers, force=True)


def run_app() -> None:
    setup_logging(to_file=True)
    if server_running():  # البرنامج مفتوح أصلًا: نفتح شباك بس
        open_window()
        return
    from montage.updater import ensure_up_to_date

    ensure_up_to_date()
    config = uvicorn.Config("montage.api:app", host=HOST, port=PORT, log_level="info", log_config=None)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server_running():
            break
        time.sleep(0.2)
    window = open_window()
    if window is None:
        thread.join()  # مالقيناش Edge: السيرفر يفضل شغال
        return
    window.wait()
    from montage import jobs

    while jobs.any_running():  # تصدير أو تجهيز شغال: نستناه يخلص
        time.sleep(2)
    server.should_exit = True
    thread.join(timeout=10)


def run_console() -> None:
    setup_logging(to_file=False)
    from montage.updater import ensure_up_to_date

    ensure_up_to_date()  # لو نزّل نسخة جديدة: يحدّث المكتبات والواجهة لوحده
    threading.Timer(1.5, lambda: webbrowser.open(URL)).start()
    uvicorn.run("montage.api:app", host=HOST, port=PORT, log_level="info", log_config=None)


if __name__ == "__main__":
    if "--app" in sys.argv:
        run_app()
    else:
        run_console()
