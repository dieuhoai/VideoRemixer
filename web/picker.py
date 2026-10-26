"""Native file picker — tkinter fallback."""
from __future__ import annotations

import sys
from pathlib import Path


def pick_directory() -> Path | None:
    try:
        if sys.platform == "darwin":
            import subprocess
            r = subprocess.run(
                ["osascript", "-e", 'POSIX path of (choose folder with prompt "Chọn thư mục")'],
                capture_output=True, text=True, timeout=60,
            )
            if r.returncode == 0 and r.stdout.strip():
                return Path(r.stdout.strip())
        else:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askdirectory(title="Chọn thư mục")
            root.destroy()
            if path:
                return Path(path)
    except Exception:
        pass
    return None


def run(mode: str = "dir", _extra: str = "") -> None:
    result = pick_directory()
    if result:
        print(str(result))
