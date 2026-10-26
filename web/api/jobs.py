"""API job: kiểm tra, xem trước timeline + tên file, chạy / dừng / theo dõi tiến độ."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from videobulkremixer.models import (
    AudioConfig,
    JobConfig,
    NamingConfig,
    SegmentConfig,
    SegmentType,
    TextRegion,
    TextReplacement,
    TextStyle,
    TransitionConfig,
    TransitionType,
)
from videobulkremixer.namer import generate_name
from videobulkremixer.orchestrator import Pipeline, list_videos
from videobulkremixer.timeline import build_timeline, joint_labels

from ..state import STATE

router = APIRouter(prefix="/api/jobs")
_STYLE_KEYS = set(TextStyle.__dataclass_fields__)


def _transition(raw: dict | None) -> TransitionConfig:
    raw = raw or {}
    return TransitionConfig(TransitionType(raw.get("type", "none")), float(raw.get("duration", 0.5)))


def parse_config(body: dict[str, Any]) -> JobConfig:
    """Đổi JSON từ giao diện thành JobConfig; lỗi dữ liệu → ValueError với câu tiếng Việt."""
    segments = []
    for s in body.get("segments", []):
        end = s.get("end")
        segments.append(SegmentConfig(
            segment_type=SegmentType(s["type"]),
            start_sec=float(s.get("start", 0) or 0),
            end_sec=float("inf") if end in (None, "") else float(end),
            source_dir=Path(s["source_dir"]),
        ))
    audio = AudioConfig(
        audio_files=[Path(p) for p in body.get("audio_files", [])],
        language_labels={str(k): str(v) for k, v in (body.get("audio_labels") or {}).items()},
    )
    texts = []
    for t in body.get("texts", []):
        r = t["region"]
        region = TextRegion(name=t.get("name") or "Vùng text", x=int(r["x"]), y=int(r["y"]),
                            width=int(r["width"]), height=int(r["height"]))
        style = TextStyle(**{k: v for k, v in (t.get("style") or {}).items() if k in _STYLE_KEYS})
        texts.append(TextReplacement(region=region, texts_by_lang={str(k): str(v) for k, v in
                                                                   (t.get("texts") or {}).items()},
                                     style=style))
    transitions = {str(k): _transition(v) for k, v in (body.get("transitions") or {}).items()}
    n = body.get("naming") or {}
    return JobConfig(
        input_dir=Path(body["input_dir"]),
        output_dir=Path(body["output_dir"]),
        segments=segments,
        transitions=transitions,
        default_transition=_transition(body.get("default_transition")),
        audio=audio,
        text_replacements=texts,
        naming=NamingConfig(appname=n.get("appname", ""), vid_prefix="VID", concept=n.get("concept", ""),
                            geo=n.get("geo") or "WW", date_str=n.get("date", "")),
    )


def _parse_or_422(body: dict[str, Any]) -> JobConfig:
    try:
        return parse_config(body)
    except (KeyError, ValueError, TypeError) as e:
        raise HTTPException(422, f"Cấu hình chưa đúng: {e}") from e


@router.post("/check")
def check(body: dict) -> dict:
    cfg = _parse_or_422(body)
    try:
        pipe = Pipeline(cfg)
        pipe.validate()
        return {"ok": True, "warnings": pipe.check_short_sources()}
    except ValueError as e:
        return {"ok": False, "error": str(e), "warnings": []}


@router.post("/timeline")
def timeline(body: dict) -> dict:
    """Chuỗi đoạn trong video gốc + tên từng mối nối (để gắn hiệu ứng)."""
    try:
        segs = [SegmentConfig(SegmentType(s["type"]), float(s.get("start", 0) or 0),
                              float("inf") if s.get("end") in (None, "") else float(s["end"]), Path("."))
                for s in body.get("segments", [])]
        parts = build_timeline(segs, float(body.get("duration", 0)))
    except (ValueError, KeyError, TypeError) as e:
        return {"ok": False, "error": str(e), "parts": [], "joints": []}
    return {"ok": True, "parts": [{"kind": p.kind, "label": p.label, "start": round(p.start, 2),
                                   "end": round(p.end, 2)} for p in parts],
            "joints": joint_labels(parts)}


@router.post("/naming")
def naming(body: dict) -> dict:
    """Xem trước tên file (tối đa 5 tên đầu)."""
    n = body.get("naming") or {}
    cfg = NamingConfig(appname=n.get("appname", ""), concept=n.get("concept", ""), geo=n.get("geo") or "WW",
                       date_str=n.get("date", ""))
    langs = [str(x) for x in body.get("languages", [])] or ["orig"]
    ratio = str(body.get("ratio") or "9x16")
    # Mỗi ngôn ngữ là 1 thư mục riêng → STT bắt đầu lại từ 001 cho từng ngôn ngữ
    names = [generate_name(cfg, lang, ratio, 1) for lang in langs[:5]]
    return {"names": names}


@router.post("")
def start(body: dict) -> dict:
    cfg = _parse_or_422(body)
    if not STATE.busy.acquire(blocking=False):
        raise HTTPException(409, "Đang có job chạy")
    try:
        Pipeline(cfg).validate()
    except ValueError as e:
        STATE.busy.release()
        raise HTTPException(422, str(e)) from e
    short = body.get("short_source", "trim")
    if short not in ("trim", "skip"):
        STATE.busy.release()
        raise HTTPException(422, "Lựa chọn source ngắn không hợp lệ")
    pipe = Pipeline(cfg, on_progress=_progress, short_source_action=short)
    STATE.pipeline = pipe
    total = len(list_videos(cfg.input_dir))
    STATE.update(status="running", done=0, total=total, current="", ok=0, failed=[], outputs=[],
                 error="", output_dir=str(cfg.output_dir), fatal="")
    threading.Thread(target=_worker, args=(pipe,), daemon=True).start()
    return {"started": True}


def _progress(done: int, total: int, name: str) -> None:
    STATE.update(done=done, total=total, current=name)


def _worker(pipe: Pipeline) -> None:
    try:
        res = pipe.run()
        outputs = []
        for it in res.items:
            rel = ""
            if it.output_path:
                rel = str(it.output_path.relative_to(Path(STATE.snapshot()["output_dir"])))
            outputs.append({"ok": it.ok, "name": it.output_path.name if it.output_path else "",
                            "path": str(it.output_path) if it.output_path else "", "rel": rel,
                            "source": it.source_video, "language": it.language, "audio": it.audio_file,
                            "transition": it.transition_used, "error": it.error, "note": it.note,
                            "duration": round(it.duration_out, 1), "size_mb": round(it.size_mb, 2)})
        failed = [{"source": o["source"], "error": o["error"]} for o in outputs if not o["ok"]]
        status = "stopped" if res.cancelled else ("error" if res.fatal else "done")
        STATE.update(status=status, ok=res.ok_count, failed=failed, outputs=outputs,
                     fatal=res.fatal, error=res.fatal)
    except Exception as e:  # noqa: BLE001
        STATE.update(status="error", error=str(e)[:300])
    finally:
        STATE.pipeline = None
        STATE.busy.release()


@router.post("/stop")
def stop() -> dict:
    p = STATE.pipeline
    if p is not None:
        p.cancel()
    return {"stopping": p is not None}


@router.get("")
def status() -> dict:
    return STATE.snapshot()


__all__ = ["router"]
