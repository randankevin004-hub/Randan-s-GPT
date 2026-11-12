"""
ui/rail.py
----------
Left icon rail: one-click AI tools (each sets a model + persona), a "more
tools" chevron, and Settings / Log out at the bottom.
"""
from __future__ import annotations

import customtkinter as ctk

from ui import theme
from ui.tools import TOOLS
from ui.widgets import icon_button


class ToolRail(ctk.CTkFrame):
    def __init__(self, master, on_tool, on_more, on_settings, on_logout) -> None:
        super().__init__(master, fg_color="transparent", width=64)
        self.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="n", padx=8)
        self._buttons: dict = {}
        for tool in TOOLS:
            b = icon_button(top, tool.icon, lambda k=tool.key: on_tool(k), box=44, tip=tool.label)
            b.pack(pady=5)
            self._buttons[tool.key] = b
        self.more = icon_button(top, "chevron_down", None, box=44, tip="More tools")
        self.more.configure(command=lambda: on_more(self.more))
        self.more.pack(pady=5)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="s", padx=8, pady=(0, 4))
        icon_button(bottom, "gear", on_settings, box=44, tip="Settings").pack(pady=5)
        icon_button(bottom, "logout", on_logout, box=44, tip="Log out").pack(pady=5)

    def set_active(self, key: str | None) -> None:
        for k, btn in self._buttons.items():
            on = k == key
            btn.configure(border_color=theme.duo("accent") if on else theme.duo("border"),
                          fg_color=theme.duo("accent_soft") if on else theme.duo("panel2"))
        extra = key is not None and key not in self._buttons
        self.more.configure(border_color=theme.duo("accent") if extra else theme.duo("border"))
