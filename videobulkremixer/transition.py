"""Tên hiệu ứng xfade của ffmpeg theo từng loại hiệu ứng trong app."""
from __future__ import annotations

from videobulkremixer.models import TransitionType

XFADE_MAP: dict[TransitionType, str] = {
    TransitionType.CROSSFADE: "fade",
    TransitionType.DISSOLVE: "dissolve",
    TransitionType.FADE_BLACK: "fadeblack",
    TransitionType.FADE_WHITE: "fadewhite",
    TransitionType.SLIDE_LR: "slideright",
    TransitionType.SLIDE_RL: "slideleft",
    TransitionType.SLIDE_UP: "slideup",
    TransitionType.SLIDE_DOWN: "slidedown",
    TransitionType.WIPE_LR: "wiperight",
    TransitionType.WIPE_RL: "wipeleft",
    TransitionType.WIPE_TB: "wipedown",
    TransitionType.WIPE_BT: "wipeup",
    TransitionType.CIRCLE_OPEN: "circleopen",
    TransitionType.ZOOM_IN: "zoomin",
}
