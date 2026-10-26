"""Tạo report.csv cho job."""
from __future__ import annotations

import csv
from pathlib import Path

from videobulkremixer.models import JobResult

COLUMNS = [
    "Tên file output",
    "Video gốc",
    "Source intro",
    "Source giữa",
    "Source outro",
    "Audio",
    "Ngôn ngữ",
    "Text thay",
    "Thời lượng gốc (s)",
    "Thời lượng output (s)",
    "Dung lượng (MB)",
    "Hiệu ứng",
    "Trạng thái",
    "Ghi chú",
]


def write_report(result: JobResult, output_dir: Path) -> Path:
    """Ghi report.csv vào output_dir."""
    report_path = output_dir / "report.csv"
    with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for item in result.items:
            status = "OK" if item.ok else f"Lỗi: {item.error}"
            writer.writerow([
                item.output_path.name if item.output_path else "",
                item.source_video,
                item.source_intro,
                item.source_mid,
                item.source_outro,
                item.audio_file or "gốc",
                item.language,
                "Có" if item.text_replaced else "Không",
                f"{item.duration_in:.1f}",
                f"{item.duration_out:.1f}",
                f"{item.size_mb:.2f}",
                item.transition_used,
                status,
                item.note,
            ])
    return report_path
