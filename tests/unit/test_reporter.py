"""Test reporter — T8."""
import csv

from videobulkremixer.models import ItemResult, JobResult
from videobulkremixer.reporter import COLUMNS, write_report


class TestWriteReport:
    def test_columns_complete(self, tmp_path):
        jr = JobResult(items=[
            ItemResult(
                output_path=tmp_path / "test.mp4", source_video="orig.mp4",
                source_intro="intro1.mp4", language="en",
                duration_in=30.0, duration_out=28.5, size_mb=12.5,
            ),
        ])
        report = write_report(jr, tmp_path)
        assert report.exists()
        with open(report, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == COLUMNS
            row = next(reader)
            assert len(row) == len(COLUMNS)

    def test_error_logged(self, tmp_path):
        jr = JobResult(items=[
            ItemResult(
                source_video="bad.mp4", ok=False,
                error="codec không hỗ trợ",
            ),
        ])
        report = write_report(jr, tmp_path)
        with open(report, encoding="utf-8-sig") as f:
            content = f.read()
            assert "Lỗi: codec không hỗ trợ" in content

    def test_trim_note_in_report(self, tmp_path):
        jr = JobResult(items=[
            ItemResult(
                output_path=tmp_path / "test.mp4", source_video="orig.mp4",
                note="source hình bị cắt từ 8.0s → 5.0s",
            ),
        ])
        report = write_report(jr, tmp_path)
        with open(report, encoding="utf-8-sig") as f:
            content = f.read()
            assert "source hình bị cắt" in content
