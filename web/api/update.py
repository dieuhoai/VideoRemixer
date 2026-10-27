"""API cập nhật: kiểm tra bản mới khi mở app, và cài bản mới khi người dùng bấm nút."""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from videobulkremixer import __version__, updater

from ..state import STATE

router = APIRouter(prefix="/api/update")
_CACHE: dict[str, Any] = {"at": 0.0, "info": None}
CACHE_SECONDS = 3600


def _latest_cached(force: bool = False) -> dict | None:
    now = time.time()
    if force or now - _CACHE["at"] > CACHE_SECONDS:
        _CACHE["info"] = updater.fetch_latest()
        _CACHE["at"] = now
    return _CACHE["info"]


@router.get("/check")
def check(force: bool = False) -> dict:
    info = _latest_cached(force)
    has = bool(info and info.get("zip_url") and updater.is_newer(info["version"]))
    return {"current": __version__, "latest": info["version"] if info else "",
            "has_update": has, "notes_url": info.get("notes_url", "") if info else "",
            "online": info is not None}


@router.post("/apply")
def apply() -> dict:
    """Tải và cài bản mới. Không cho cài khi đang chạy job, vì file app sẽ bị thay."""
    if STATE.snapshot().get("status") == "running":
        raise HTTPException(409, "Đang chạy xử lý video. Đợi xong rồi mới cập nhật.")
    if not STATE.busy.acquire(blocking=False):
        raise HTTPException(409, "Đang chạy xử lý video. Đợi xong rồi mới cập nhật.")
    work = Path(tempfile.mkdtemp(prefix="vrm_update_"))
    try:
        info = _latest_cached(force=True)
        if not info or not info.get("zip_url") or not updater.is_newer(info["version"]):
            raise HTTPException(409, "Hiện không có bản mới hơn.")
        zip_path = work / "update.zip"
        updater.download(info["zip_url"], zip_path)
        staged = work / "staged"
        updater.safe_extract(zip_path, staged)
        app_root = Path(__file__).resolve().parents[2]
        updated = updater.apply_update(staged, app_root)
    except updater.UpdateError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        STATE.busy.release()
        shutil.rmtree(work, ignore_errors=True)
    _CACHE["at"] = 0.0
    return {"ok": True, "version": info["version"], "updated": updated,
            "message": "Đã cập nhật lên bản " + info["version"] + ". Đóng cửa sổ này rồi mở lại app."}
