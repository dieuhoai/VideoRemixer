"""Điểm vào dùng chung cho CLI và web: chạy 1 job với callback tiến độ."""
from __future__ import annotations

from collections.abc import Callable

from videobulkremixer.models import JobConfig, JobResult
from videobulkremixer.orchestrator import Pipeline


def run_job(
    config: JobConfig,
    on_progress: Callable[[int, int, str], None] | None = None,
    short_source_action: str = "trim",
) -> JobResult:
    return Pipeline(config=config, on_progress=on_progress, short_source_action=short_source_action).run()
