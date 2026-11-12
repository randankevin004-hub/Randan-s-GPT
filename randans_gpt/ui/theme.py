"""
ui/theme.py
-----------
Green "neon glass" palettes (dark + light) shared by every UI component.

CustomTkinter widgets accept a (light, dark) colour tuple and switch
automatically when the appearance mode changes -> use `duo(key)` for them.
Plain tkinter widgets (Text, Canvas) need a single colour -> `pal(key)`.
"""
from __future__ import annotations

import customtkinter as ctk

FONT_FAMILY = "Segoe UI"
CODE_FONT = "Consolas"

PALETTES = {
    "Dark": {
        "bg": "#030605", "panel": "#070b09", "panel2": "#0b110e", "input_bg": "#0b110e",
        "border": "#1c3025", "text": "#eaf3ed", "muted": "#7d9185", "icon": "#dfeee4",
        "accent": "#3ddc57", "accent2": "#c6f135", "accent_hover": "#2dbf45",
        "accent_soft": "#0f2418", "hover": "#111c16", "danger": "#ef5350",
        "success": "#3ddc57",
        "user_bg": "#14462a", "user_fg": "#f2fff6", "ai_bg": "#0b110e", "ai_fg": "#e6efe9",
        "error_bg": "#3a1c22", "error_fg": "#ffb4b9",
        "code_bg": "#040706", "code_fg": "#d6e8dc", "think_fg": "#7d9185",
        "syn_keyword": "#c792ea", "syn_string": "#c3e88d", "syn_comment": "#637777",
        "syn_number": "#f78c6c", "syn_func": "#82aaff", "syn_class": "#ffcb6b",
        "syn_op": "#89ddff", "syn_builtin": "#7fdbca",
    },
    "Light": {
        "bg": "#dde9df", "panel": "#f6faf7", "panel2": "#ffffff", "input_bg": "#ffffff",
        "border": "#c3d8c9", "text": "#102016", "muted": "#5d7364", "icon": "#17321f",
        "accent": "#1faa3c", "accent2": "#8fcf1a", "accent_hover": "#168a2f",
        "accent_soft": "#dff3e4", "hover": "#e6f1e9", "danger": "#d6333a",
        "success": "#1a7f37",
        "user_bg": "#1faa3c", "user_fg": "#ffffff", "ai_bg": "#e9f2ec", "ai_fg": "#102016",
        "error_bg": "#fde8ea", "error_fg": "#a3262d",
        "code_bg": "#d8e6dc", "code_fg": "#102016", "think_fg": "#5d7364",
        "syn_keyword": "#7c3aed", "syn_string": "#15803d", "syn_comment": "#6b7280",
        "syn_number": "#c2410c", "syn_func": "#1d4ed8", "syn_class": "#b45309",
        "syn_op": "#0369a1", "syn_builtin": "#0f766e",
    },
}

_current = "Dark"


def set_theme(name: str) -> None:
    """Activate "Dark" or "Light" for CustomTkinter and for pal()."""
    global _current
    _current = name if name in PALETTES else "Dark"
    ctk.set_appearance_mode(_current.lower())


def current_name() -> str:
    return _current


def pal(key: str) -> str:
    """Single colour for the active theme (for plain tkinter widgets)."""
    return PALETTES[_current][key]


def duo(key: str) -> tuple:
    """(light, dark) tuple understood by CustomTkinter widgets."""
    return (PALETTES["Light"][key], PALETTES["Dark"][key])
