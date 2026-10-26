"""Dòng lệnh: python -m videobulkremixer run <thư_mục_gốc> <thư_mục_output> [tuỳ chọn]."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from videobulkremixer.models import (
    AudioConfig,
    JobConfig,
    NamingConfig,
    SegmentConfig,
    SegmentType,
    TransitionConfig,
    TransitionType,
)
from videobulkremixer.processor import run_job


def _segment(kind: SegmentType, raw: str) -> SegmentConfig:
    """Định dạng: intro=END:DIR · custom=START:END:DIR · outro=START:DIR (END bỏ trống = hết video)."""
    parts = raw.split(":")
    if kind == SegmentType.INTRO:
        start, end, folder = 0.0, float(parts[0]), ":".join(parts[1:])
    elif kind == SegmentType.CUSTOM:
        start, end, folder = float(parts[0]), float(parts[1]), ":".join(parts[2:])
    else:
        start, end, folder = float(parts[0]), float("inf"), ":".join(parts[1:])
    return SegmentConfig(kind, start, end, Path(folder))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="videobulkremixer", description="Video Bulk Remixer — dòng lệnh")
    sub = ap.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Chạy một job")
    run.add_argument("input_dir", type=Path, help="Thư mục video gốc")
    run.add_argument("output_dir", type=Path, help="Thư mục output")
    run.add_argument("--intro", metavar="END:DIR", help="Thay đoạn đầu từ 0 đến END giây")
    run.add_argument("--custom", metavar="START:END:DIR", help="Thay đoạn giữa từ START đến END giây")
    run.add_argument("--outro", metavar="START:DIR", help="Thay đoạn cuối từ START giây đến hết")
    run.add_argument("--audio", action="append", default=[], type=Path, help="File audio thay thế (lặp lại được)")
    run.add_argument("--transition", default="none", choices=[t.value for t in TransitionType])
    run.add_argument("--transition-duration", type=float, default=0.5)
    run.add_argument("--short", choices=["trim", "skip"], default="trim",
                     help="Source ngắn hơn đoạn: co đoạn hoặc bỏ qua")
    run.add_argument("--appname", default="")
    run.add_argument("--concept", default="")
    run.add_argument("--geo", default="WW")
    run.add_argument("--date", default="", help="ddmmyy (mặc định: hôm nay)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input_dir.is_dir():
        print(f"Lỗi: {args.input_dir} không phải thư mục", file=sys.stderr)
        return 1
    segments: list[SegmentConfig] = []
    if args.intro:
        segments.append(_segment(SegmentType.INTRO, args.intro))
    if args.custom:
        segments.append(_segment(SegmentType.CUSTOM, args.custom))
    if args.outro:
        segments.append(_segment(SegmentType.OUTRO, args.outro))
    config = JobConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        segments=segments,
        audio=AudioConfig(audio_files=list(args.audio)),
        default_transition=TransitionConfig(TransitionType(args.transition), args.transition_duration),
        naming=NamingConfig(appname=args.appname, concept=args.concept, geo=args.geo, date_str=args.date),
    )

    def progress(cur: int, total: int, name: str) -> None:
        print(f"[{cur}/{total}] {name}", flush=True)

    try:
        result = run_job(config, progress, short_source_action=args.short)
    except ValueError as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        return 1
    print(f"Xong: {result.ok_count}/{result.total} video thành công. Báo cáo: {args.output_dir / 'report.csv'}")
    if result.fatal:
        print(result.fatal, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
