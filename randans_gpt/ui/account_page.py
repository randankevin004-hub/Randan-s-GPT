"""ui/account_page.py - profile: name, photo and a few personal stats."""
from __future__ import annotations

import customtkinter as ctk

from ui import graphics, theme


class AccountPage(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, corner_radius=24, border_width=1, border_color=theme.duo("border"),
                         fg_color=theme.duo("panel"))
        self.app = app
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.place(relx=0.5, rely=0.06, anchor="n")

        ctk.CTkLabel(box, text="Account", font=ctk.CTkFont(size=26, weight="bold")).pack(pady=(0, 16))
        self.avatar = ctk.CTkLabel(box, text="")
        self.avatar.pack()
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(pady=10)
        self._btn(row, "Change photo", app.change_avatar).pack(side="left", padx=5)
        self._btn(row, "Remove photo", app.remove_avatar).pack(side="left", padx=5)

        ctk.CTkLabel(box, text="Display name", text_color=theme.duo("muted"), anchor="w").pack(fill="x", pady=(16, 2))
        self.name = ctk.CTkEntry(box, width=320, height=40, corner_radius=14, fg_color=theme.duo("panel2"),
                                 border_color=theme.duo("border"))
        self.name.pack()
        self.name.bind("<Return>", lambda e: self._save())
        ctk.CTkButton(box, text="Save profile", width=320, height=40, corner_radius=20,
                      fg_color=theme.duo("accent"), hover_color=theme.duo("accent_hover"), text_color="#04140a",
                      command=self._save).pack(pady=(12, 4))
        self.msg = ctk.CTkLabel(box, text="", text_color=theme.duo("accent"))
        self.msg.pack()
        self.stats = ctk.CTkLabel(box, text="", text_color=theme.duo("muted"), justify="center")
        self.stats.pack(pady=(14, 0))
        row2 = ctk.CTkFrame(box, fg_color="transparent")
        row2.pack(pady=14)
        self._btn(row2, "Settings", lambda: app.show_page("settings")).pack(side="left", padx=5)
        self._btn(row2, "Log out", app.logout).pack(side="left", padx=5)

    @staticmethod
    def _btn(master, text, cmd):
        return ctk.CTkButton(master, text=text, height=34, corner_radius=17, fg_color=theme.duo("panel2"),
                             hover_color=theme.duo("hover"), border_width=1, border_color=theme.duo("border"),
                             text_color=theme.duo("text"), command=cmd)

    def _save(self) -> None:
        self.app.set_user_name(self.name.get())
        self.msg.configure(text="Profile saved \u2713")
        self.after(2000, lambda: self.msg.configure(text=""))

    def refresh(self, name: str, avatar_path: str, stats: dict, member_since: str) -> None:
        self.avatar.configure(image=graphics.avatar_image(avatar_path, name, 110))
        self.name.delete(0, "end")
        self.name.insert(0, name)
        since = f"Member since {member_since}\n" if member_since else ""
        self.stats.configure(text=f"{since}{stats['chats']} chats  \u2022  {stats['questions']} questions  \u2022  "
                                  f"{stats['memories']} memories")
