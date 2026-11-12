"""
ui/navbar.py
------------
Top bar: logo, pill navigation (Dashboard / AI Chat / Help / Account) and the
right pill with theme toggle, history toggle, notifications bell and avatar.
"""
from __future__ import annotations

import customtkinter as ctk

from ui import graphics, theme
from ui.widgets import Tooltip, icon_button

NAV = (("dashboard", "Dashboard"), ("chat", "AI Chat"), ("help", "Help"), ("account", "Account"))


class NavBar(ctk.CTkFrame):
    def __init__(self, master, on_nav, on_theme, on_history, on_bell, on_avatar) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(2, weight=1)
        self._buttons: dict = {}
        self._on_theme = on_theme

        ctk.CTkLabel(self, text="", image=graphics.logo_image(38)).grid(row=0, column=0, padx=(6, 14), pady=10)

        pill = ctk.CTkFrame(self, corner_radius=26, border_width=1, border_color=theme.duo("border"),
                            fg_color=theme.duo("panel"))
        pill.grid(row=0, column=1, pady=10)
        for key, label in NAV:
            btn = ctk.CTkButton(pill, text=label, width=96, height=38, corner_radius=19,
                                fg_color="transparent", hover_color=theme.duo("hover"),
                                border_width=1, border_color=theme.duo("panel"),
                                text_color=theme.duo("text"), command=lambda k=key: on_nav(k))
            btn.pack(side="left", padx=4, pady=5)
            self._buttons[key] = btn

        right = ctk.CTkFrame(self, corner_radius=26, border_width=1, border_color=theme.duo("border"),
                             fg_color=theme.duo("panel"))
        right.grid(row=0, column=3, pady=10, padx=(0, 6))
        self.sun = icon_button(right, "sun", lambda: on_theme("Light"), box=36, tip="Light theme")
        self.moon = icon_button(right, "moon", lambda: on_theme("Dark"), box=36, tip="Dark theme")
        self.sun.pack(side="left", padx=(8, 2), pady=6)
        self.moon.pack(side="left", padx=(2, 10), pady=6)
        icon_button(right, "chat", on_history, box=36, tip="Show / hide chat history").pack(side="left", padx=3)
        self.bell = icon_button(right, "bell", on_bell, box=36, tip="Notifications")
        self.bell.pack(side="left", padx=3)
        self.dot = ctk.CTkLabel(right, text="", width=9, height=9, corner_radius=5, fg_color=theme.duo("danger"))
        self.avatar = ctk.CTkButton(right, text="", width=40, height=40, corner_radius=20, fg_color="transparent",
                                    hover_color=theme.duo("hover"), command=on_avatar)
        self.avatar.pack(side="left", padx=(6, 8), pady=5)
        Tooltip(self.avatar, "Your profile")

    def set_active(self, page: str | None) -> None:
        for key, btn in self._buttons.items():
            on = key == page
            btn.configure(fg_color=theme.duo("panel2") if on else "transparent",
                          border_color=theme.duo("accent") if on else theme.duo("panel"),
                          text_color=theme.duo("accent") if on else theme.duo("text"))

    def set_theme_buttons(self, mode: str) -> None:
        for btn, on in ((self.sun, mode == "Light"), (self.moon, mode == "Dark")):
            btn.configure(border_color=theme.duo("accent") if on else theme.duo("border"),
                          fg_color=theme.duo("accent_soft") if on else theme.duo("panel2"))

    def set_unread(self, count: int) -> None:
        if count > 0:
            self.dot.place(in_=self.bell, relx=0.68, rely=0.10)
            self.dot.lift()
        else:
            self.dot.place_forget()

    def set_avatar(self, image) -> None:
        self.avatar.configure(image=image)
