"""
ui/history_panel.py
-------------------
Right "History Chat" panel: New Chat button and chats grouped by day
(Today / Yesterday / N Days Ago / Older).
"""
from __future__ import annotations

from datetime import datetime

import customtkinter as ctk

from ui import icons, theme


def group_label(updated_at: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    try:
        days = (now.date() - datetime.fromisoformat(updated_at).date()).days
    except ValueError:
        return "Older"
    if days <= 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    return f"{days} Days Ago" if days < 30 else "Older"


class HistoryPanel(ctk.CTkFrame):
    WIDTH = 300

    def __init__(self, master, on_new, on_select, on_menu) -> None:
        super().__init__(master, width=self.WIDTH, corner_radius=24, border_width=1,
                         border_color=theme.duo("border"), fg_color=theme.duo("panel"))
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._on_select, self._on_menu = on_select, on_menu

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 6))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="History Chat", anchor="w",
                     font=ctk.CTkFont(size=18)).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(head, text=" New Chat", image=icons.icon("plus", 16), compound="left", width=104,
                      height=36, corner_radius=18, fg_color=theme.duo("panel2"), hover_color=theme.duo("hover"),
                      border_width=1, border_color=theme.duo("border"), text_color=theme.duo("text"),
                      command=on_new).grid(row=0, column=1)

        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.list.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 12))

    def refresh(self, chats: list, active_id: int | None) -> None:
        for child in self.list.winfo_children():
            child.destroy()
        if not chats:
            ctk.CTkLabel(self.list, text="No chats yet.\nStart a conversation!",
                         text_color=theme.duo("muted")).pack(pady=30)
            return
        last = None
        for chat in chats:
            label = group_label(chat["updated_at"])
            if label != last:
                ctk.CTkLabel(self.list, text=label, anchor="w", text_color=theme.duo("text"),
                             font=ctk.CTkFont(size=13)).pack(fill="x", padx=10, pady=(12, 4))
                last = label
            self._row(chat, chat["id"] == active_id)

    def _row(self, chat: dict, active: bool) -> None:
        row = ctk.CTkFrame(self.list, corner_radius=16, border_width=1,
                           border_color=theme.duo("accent") if active else theme.duo("border"),
                           fg_color=theme.duo("accent_soft") if active else theme.duo("panel2"))
        row.pack(fill="x", padx=4, pady=3)
        title = chat["title"] if len(chat["title"]) <= 22 else chat["title"][:21] + "\u2026"
        btn = ctk.CTkButton(row, text="  " + title, anchor="w", height=44, corner_radius=16,
                            image=icons.icon("history", 18), compound="left", fg_color="transparent",
                            hover_color=theme.duo("hover"), text_color=theme.duo("text"),
                            command=lambda cid=chat["id"]: self._on_select(cid))
        btn.pack(side="left", fill="x", expand=True, padx=(4, 0), pady=4)
        more = ctk.CTkButton(row, text="", image=icons.icon("dots", 16), width=30, height=30, corner_radius=15,
                             fg_color="transparent", hover_color=theme.duo("hover"))
        more.configure(command=lambda b=more, cid=chat["id"]: self._on_menu(b, cid))
        more.pack(side="right", padx=(0, 8))
        btn.bind("<Button-3>", lambda e, b=more, cid=chat["id"]: self._on_menu(b, cid))
