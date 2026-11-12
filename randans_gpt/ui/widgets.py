"""
ui/widgets.py
-------------
Small reusable widgets: Tooltip, Popover (floating menus / panels) and the
circular icon button used all over the interface.
"""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ui import icons, theme


class Tooltip:
    """Tiny hover tooltip."""

    def __init__(self, widget, text: str) -> None:
        self.widget, self.text, self._job, self._tip = widget, text, None, None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._hide, add="+")

    def _schedule(self, _e=None) -> None:
        self._hide()
        self._job = self.widget.after(500, self._show)

    def _show(self) -> None:
        try:
            x = self.widget.winfo_rootx() + 8
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
            self._tip = tk.Toplevel(self.widget)
            self._tip.wm_overrideredirect(True)
            self._tip.wm_geometry(f"+{x}+{y}")
            tk.Label(self._tip, text=self.text, bg=theme.pal("panel2"), fg=theme.pal("text"),
                     bd=1, relief="solid", padx=8, pady=3, font=(theme.FONT_FAMILY, 9)).pack()
        except tk.TclError:
            self._tip = None

    def _hide(self, _e=None) -> None:
        if self._job:
            try:
                self.widget.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


class Popover(ctk.CTkFrame):
    """A floating panel placed over the window next to an anchor widget.
    Closes on outside click or Escape. Only one is open at a time."""

    _current: "Popover | None" = None

    @classmethod
    def close_current(cls) -> None:
        if cls._current is not None:
            cls._current.close()

    @classmethod
    def show(cls, anchor, build, width: int = 230, align: str = "left", side: str = "below") -> "Popover":
        cls.close_current()
        root = anchor.winfo_toplevel()
        pop = cls(root, anchor, width)
        build(pop, pop.close)
        pop.update_idletasks()
        pop._place(align, side)
        cls._current = pop
        return pop

    def __init__(self, root, anchor, width: int) -> None:
        super().__init__(root, width=width, corner_radius=16, border_width=1,
                         border_color=theme.duo("border"), fg_color=theme.duo("panel2"))
        self.root, self.anchor, self._width = root, anchor, width
        self._bind_id = root.bind("<Button-1>", self._outside, add="+")
        self._esc_id = root.bind("<Escape>", lambda e: self.close(), add="+")

    def _place(self, align: str, side: str) -> None:
        r = self.root
        ax = self.anchor.winfo_rootx() - r.winfo_rootx()
        ay = self.anchor.winfo_rooty() - r.winfo_rooty()
        aw, ah = self.anchor.winfo_width(), self.anchor.winfo_height()
        w, h = max(self._width, self.winfo_reqwidth()), self.winfo_reqheight()
        if side == "right":
            x, y = ax + aw + 8, ay
        else:
            x = ax if align == "left" else ax + aw - w
            y = ay + ah + 8
        x = max(8, min(x, r.winfo_width() - w - 8))
        y = max(8, min(y, r.winfo_height() - h - 8))
        self.place(x=x, y=y)
        self.lift()

    def _outside(self, event) -> None:
        w = event.widget
        while w is not None:
            if w is self or w is self.anchor:
                return
            w = getattr(w, "master", None)
        self.close()

    def close(self) -> None:
        try:
            self.root.unbind("<Button-1>", self._bind_id)
            self.root.unbind("<Escape>", self._esc_id)
        except tk.TclError:
            pass
        if Popover._current is self:
            Popover._current = None
        try:
            self.destroy()
        except tk.TclError:
            pass


def add_menu_items(frame, items: list, close, width: int = 210) -> None:
    """items: (label, icon_name|None, callback, opts{danger,checked}) tuples."""
    for label, icon_name, cb, *rest in items:
        opts = rest[0] if rest else {}
        color = theme.duo("danger") if opts.get("danger") else theme.duo("text")
        ctk.CTkButton(
            frame, text=("  " + label), anchor="w", width=width, height=34, corner_radius=10,
            image=icons.icon(icon_name, 16, color=None if not opts.get("danger") else theme.pal("danger"))
            if icon_name else None, compound="left", fg_color=theme.duo("accent_soft") if opts.get("checked") else "transparent",
            hover_color=theme.duo("hover"), text_color=color,
            command=lambda c=cb: (close(), c()),
        ).pack(padx=6, pady=2)
    # small bottom padding
    ctk.CTkFrame(frame, height=4, fg_color="transparent").pack()


def icon_button(master, name: str, command=None, size: int = 18, box: int = 38,
                ring: bool = True, tip: str | None = None, **kw) -> ctk.CTkButton:
    """Round icon button with optional ring + tooltip."""
    btn = ctk.CTkButton(
        master, text="", image=icons.icon(name, size), width=box, height=box,
        corner_radius=box // 2, fg_color=theme.duo("panel2") if ring else "transparent",
        hover_color=theme.duo("hover"), border_width=1 if ring else 0,
        border_color=theme.duo("border"), command=command, **kw)
    if tip:
        Tooltip(btn, tip)
    return btn
