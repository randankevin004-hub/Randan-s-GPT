"""
ui/welcome.py
-------------
Welcome screen: glowing gradient background, animated green orb and the
greeting, all drawn on one Canvas (so the text is truly transparent).
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from PIL import ImageTk

from ui import graphics, theme

ARCS = (  # radius factor, width, colour key, speed deg/frame, extent
    (1.00, 3, "accent", 3.0, 250),
    (0.88, 2, "accent2", -4.5, 200),
    (0.76, 3, "accent", 5.5, 150),
    (0.64, 2, "accent2", -2.0, 300),
)


class WelcomeCanvas(tk.Canvas):
    def __init__(self, master, on_layout) -> None:
        super().__init__(master, highlightthickness=0, bd=0, bg=theme.pal("panel"))
        self._on_layout = on_layout          # callback(center_x, input_top_y, width)
        self.greeting = ""
        self._angle = 0.0
        self._imgs: list = []
        self._arc_ids: list = []
        self._job = None
        self._font = tkfont.Font(family=theme.FONT_FAMILY, size=22)
        self.bind("<Configure>", self._schedule_layout)
        self._tick()

    def set_greeting(self, text: str) -> None:
        self.greeting = text
        self.itemconfigure("greeting", text=text)

    def refresh_theme(self) -> None:
        self.configure(bg=theme.pal("panel"))
        self._layout()

    def _schedule_layout(self, _e=None) -> None:
        if self._job:
            self.after_cancel(self._job)
        self._job = self.after(60, self._layout)

    def _layout(self) -> None:
        self._job = None
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50 or h < 50:
            return
        mode = theme.current_name()
        self.delete("all")
        self._imgs.clear()
        self._arc_ids.clear()

        bg = ImageTk.PhotoImage(graphics.welcome_bg(w, h, mode))
        self._imgs.append(bg)
        self.create_image(0, 0, image=bg, anchor="nw")

        radius = max(34, min(62, int(h * 0.13)))
        cx, cy = w / 2, max(radius + 30, h * 0.24)
        core = ImageTk.PhotoImage(graphics.orb_core(int(radius * 3.4), mode))
        self._imgs.append(core)
        self.create_image(cx, cy, image=core)
        for factor, width, key, _speed, extent in ARCS:
            r = radius * factor * 0.98
            self._arc_ids.append(self.create_arc(
                cx - r, cy - r, cx + r, cy + r, start=0, extent=extent, style="arc",
                outline=theme.pal(key), width=width))

        ty = cy + radius + 52
        self.create_text(cx, ty, text=self.greeting, tags="greeting", fill=theme.pal("text"),
                         font=self._font, width=min(w - 60, 520), justify="center")
        self._on_layout(cx, ty + 52, min(660, int(w * 0.84)))

    def _tick(self) -> None:
        try:
            if self._arc_ids and self.winfo_viewable():
                self._angle += 1
                for item, (_f, _w, _k, speed, _e) in zip(self._arc_ids, ARCS):
                    self.itemconfigure(item, start=(self._angle * speed) % 360)
            self._tick_job = self.after(55, self._tick)
        except tk.TclError:
            pass
