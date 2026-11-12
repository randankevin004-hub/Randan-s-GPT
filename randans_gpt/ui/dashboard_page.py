"""ui/dashboard_page.py - usage statistics, drawn with plain Canvas bars."""
from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta

import customtkinter as ctk

from models.router import label_for
from ui import icons, theme


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, corner_radius=24, border_width=1, border_color=theme.duo("border"),
                         fg_color=theme.duo("panel"))
        self.app = app
        self.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="c")
        ctk.CTkLabel(self, text="Dashboard", font=ctk.CTkFont(size=26, weight="bold"), anchor="w"
                     ).grid(row=0, column=0, columnspan=4, sticky="w", padx=28, pady=(24, 2))
        self.sub = ctk.CTkLabel(self, text="", text_color=theme.duo("muted"), anchor="w")
        self.sub.grid(row=1, column=0, columnspan=4, sticky="w", padx=28, pady=(0, 10))
        self.cards: dict = {}
        for i, (key, label, icon) in enumerate((("chats", "Chats", "chat"), ("questions", "Questions asked", "user"),
                                                ("messages", "Total messages", "lines"), ("memories", "Memories", "note"))):
            card = ctk.CTkFrame(self, corner_radius=18, border_width=1, border_color=theme.duo("border"),
                                fg_color=theme.duo("panel2"))
            card.grid(row=2, column=i, sticky="new", padx=10 if 0 < i < 3 else (28 if i == 0 else 10, 10 if i < 3 else 28), pady=6)
            ctk.CTkLabel(card, text="", image=icons.icon(icon, 20)).pack(anchor="w", padx=16, pady=(14, 0))
            num = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=30, weight="bold"), text_color=theme.duo("accent"))
            num.pack(anchor="w", padx=16)
            ctk.CTkLabel(card, text=label, text_color=theme.duo("muted")).pack(anchor="w", padx=16, pady=(0, 14))
            self.cards[key] = num

        self.grid_rowconfigure(3, weight=1)
        self.week = self._panel("Questions - last 7 days", 3, 0, 2)
        self.models = self._panel("Model usage", 3, 2, 2)
        self.week_canvas = tk.Canvas(self.week, height=190, highlightthickness=0, bd=0, bg=theme.pal("panel2"))
        self.week_canvas.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._week_data: tuple = ({}, )
        self.week_canvas.bind("<Configure>", lambda e: self._draw_week())
        self.model_box = ctk.CTkFrame(self.models, fg_color="transparent")
        self.model_box.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.status = ctk.CTkLabel(self, text="", anchor="w", text_color=theme.duo("muted"), wraplength=900, justify="left")
        self.status.grid(row=4, column=0, columnspan=4, sticky="w", padx=28, pady=(0, 18))

    def _panel(self, title, row, col, span):
        f = ctk.CTkFrame(self, corner_radius=18, border_width=1, border_color=theme.duo("border"),
                         fg_color=theme.duo("panel2"))
        f.grid(row=row, column=col, columnspan=span, sticky="nsew", padx=(28 if col == 0 else 10, 28 if col + span == 4 else 10), pady=6)
        ctk.CTkLabel(f, text=title, anchor="w", font=ctk.CTkFont(size=14, weight="bold")).pack(fill="x", padx=16, pady=(12, 6))
        return f

    def _draw_week(self) -> None:
        """Bar chart of questions per day (redrawn on resize)."""
        c = self.week_canvas
        c.configure(bg=theme.pal("panel2"))
        c.delete("all")
        w, h = max(300, c.winfo_width()), max(150, c.winfo_height())
        days = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
        vals = [self._week_data[0].get(d.isoformat(), 0) for d in days]
        top = max(vals + [1])
        slot = (w - 30) / 7
        for i, (d, v) in enumerate(zip(days, vals)):
            x0 = 15 + i * slot + slot * 0.22
            x1 = 15 + (i + 1) * slot - slot * 0.22
            bh = (h - 50) * v / top
            c.create_rectangle(x0, h - 28 - bh, x1, h - 28, fill=theme.pal("accent") if v else theme.pal("border"), width=0)
            c.create_text((x0 + x1) / 2, h - 12, text=d.strftime("%a"), fill=theme.pal("muted"), font=(theme.FONT_FAMILY, 9))
            if v:
                c.create_text((x0 + x1) / 2, h - 34 - bh, text=str(v), fill=theme.pal("text"), font=(theme.FONT_FAMILY, 9))

    def refresh(self, stats: dict, online: bool, installed: list) -> None:
        self.sub.configure(text=f"Welcome back, {self.app.settings.get('user_name')}. Here's your activity.")
        for key, lab in self.cards.items():
            lab.configure(text=str(stats[key]))
        self._week_data = (stats["daily"],)
        self._draw_week()
        # --- per-model usage
        for child in self.model_box.winfo_children():
            child.destroy()
        rows = stats["by_model"]
        if not rows:
            ctk.CTkLabel(self.model_box, text="No answers yet - ask something!", text_color=theme.duo("muted")).pack(pady=20)
        total = max(1, sum(r["c"] for r in rows))
        for r in rows[:5]:
            line = ctk.CTkFrame(self.model_box, fg_color="transparent")
            line.pack(fill="x", pady=4)
            ctk.CTkLabel(line, text=label_for(r["model"]), anchor="w", width=130).pack(side="left")
            bar = ctk.CTkProgressBar(line, height=10, progress_color=theme.duo("accent"), fg_color=theme.duo("border"))
            bar.set(r["c"] / total)
            bar.pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkLabel(line, text=str(r["c"]), width=30).pack(side="left")
        state = "online" if online else "offline - start the Ollama app"
        self.status.configure(text=f"Ollama is {state}.  Installed models: " + (", ".join(installed) or "none detected"))
