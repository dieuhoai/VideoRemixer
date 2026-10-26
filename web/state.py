"""Trạng thái job đang chạy — một job tại một thời điểm, UI đọc bằng polling."""
from __future__ import annotations

import threading
from typing import Any


class AppState:
    def __init__(self) -> None:
        self.token = ""
        self._lock = threading.Lock()
        self._job: dict[str, Any] = {"status": "idle", "done": 0, "total": 0, "current": "", "ok": 0,
                                     "failed": [], "outputs": [], "error": "", "output_dir": ""}
        self.pipeline: Any = None
        self.busy = threading.Lock()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._job)

    def update(self, **kw: Any) -> None:
        with self._lock:
            self._job.update(kw)


STATE = AppState()
