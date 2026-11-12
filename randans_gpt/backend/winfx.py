"""Windows-only polish: window icon and a title bar that matches the theme (best effort)."""
from __future__ import annotations

import sys

CAPTION = {"dark": 0x050603, "light": 0xE8EFE6}      # COLORREF 0x00BBGGRR of #030605 / #e6efe8


def _hwnd(window):
    try:
        return int(window.native.Handle.ToInt64())
    except Exception:  # noqa: BLE001
        return None


def apply_window_style(window, dark: bool, icon_path: str | None = None) -> None:
    if sys.platform != "win32":
        return
    hwnd = _hwnd(window)
    if not hwnd:
        return
    try:
        import ctypes
        from ctypes import byref, c_int
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute(hwnd, 20, byref(c_int(1 if dark else 0)), 4)      # dark title bar
        dwm.DwmSetWindowAttribute(hwnd, 35, byref(c_int(CAPTION["dark" if dark else "light"])), 4)  # Win11 caption colour
        if icon_path:
            user32 = ctypes.windll.user32
            for kind, size in ((0, 16), (1, 32)):                                     # small + big icon
                hicon = user32.LoadImageW(None, icon_path, 1, size, size, 0x10)
                if hicon:
                    user32.SendMessageW(hwnd, 0x80, kind, hicon)
    except Exception:  # noqa: BLE001 - purely cosmetic
        pass
