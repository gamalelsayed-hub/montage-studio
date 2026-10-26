"""شغل طويل في الخلفية (تفريغ، تجهيز، تصدير) والواجهة بتسأل عن نسبته."""

from __future__ import annotations

import logging
import threading
import traceback
import uuid
from typing import Callable

log = logging.getLogger(__name__)

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


class JobContext:
    def __init__(self, job: dict):
        self.job = job

    def update(self, progress: float | None = None, message: str | None = None) -> None:
        with _lock:
            if progress is not None:
                self.job["progress"] = round(max(0.0, min(progress, 1.0)), 3)
            if message is not None:
                self.job["message"] = message


def start(project_id: str, kind: str, work: Callable[[JobContext], dict | None]) -> dict:
    with _lock:
        for job in _jobs.values():
            if job["project_id"] == project_id and job["status"] == "running":
                raise RuntimeError("فيه شغل لسه شغال على المشروع ده. استنى لما يخلص.")
        job = {"id": uuid.uuid4().hex[:10], "project_id": project_id, "kind": kind,
               "status": "running", "progress": 0.0, "message": "بنبدأ…", "error": None,
               "result": None}
        _jobs[job["id"]] = job

    def runner() -> None:
        ctx = JobContext(job)
        try:
            result = work(ctx)
            with _lock:
                job.update(status="done", progress=1.0, result=result, message="خلص ✓")
        except Exception as exc:
            log.error("job %s failed\n%s", job["id"], traceback.format_exc())
            with _lock:
                job.update(status="error", error=str(exc), message="حصلت مشكلة")

    threading.Thread(target=runner, daemon=True).start()
    return dict(job)


def get(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def for_project(project_id: str) -> list[dict]:
    with _lock:
        return [dict(j) for j in _jobs.values() if j["project_id"] == project_id]
