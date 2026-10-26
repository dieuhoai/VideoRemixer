"""Tên hiệu ứng xfade của ffmpeg theo từng loại hiệu ứng trong app."""
from __future__ import annotations

from videobulkremixer.models import TransitionType

XFADE_MAP: dict[TransitionType, str] = {
    TransitionType.CROSSFADE: "fade",
    TransitionType.FADE_BLACK: "fadeblack",
    TransitionType.FADE_WHITE: "fadewhite",
    TransitionType.SLIDE_LR: "slideright",  # lớp mới trượt từ trái sang phải
    TransitionType.SLIDE_RL: "slideleft",  # lớp mới trượt từ phải sang trái
    TransitionType.WIPE_TB: "wipedown",
    TransitionType.WIPE_BT: "wipeup",
}
