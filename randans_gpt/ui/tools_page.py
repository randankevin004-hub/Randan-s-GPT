"""
ui/tools_page.py
----------------
Manage MCP tool servers: import them from Codex (e.g. REA), add one by hand,
connect / disconnect, enable or remove them.
"""
from __future__ import annotations

import shlex
import sys

import customtkinter as ctk

from ui import icons, theme

STATUS = {"connected": ("Connected", "success"), "connecting": ("Connecting...", "muted"),
          "error": ("Error", "danger"), "idle": ("Not connected", "muted"), "stopped": ("Stopped", "muted")}


class ToolsPage(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, corner_radius=24, border_width=1, border_color=theme.duo("border"),
                         fg_color=theme.duo("panel"))
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(self, text="Tool servers", font=ctk.CTkFont(size=26, weight="bold"), anchor="w"
                     ).grid(row=0, column=0, sticky="w", padx=28, pady=(22, 0))
        ctk.CTkLabel(self, anchor="w", justify="left", text_color=theme.duo("muted"), wraplength=820,
                     text="MCP servers (like REA) give the model extra abilities. Import the ones you set up for "
                          "Codex, turn on the Tools button in the chat, and ask for something the tools can do. "
                          "Use a tool-capable model such as Qwen 2.5, Qwen3.5 or Llama 3.2."
                     ).grid(row=1, column=0, sticky="w", padx=28, pady=(2, 10))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="w", padx=24)
        for text, cmd, accent in (("Import from Codex", app.mcp_import_codex, True),
                                  ("Add server", self._add_dialog, False),
                                  ("Connect all", app.mcp_connect_all, False)):
            ctk.CTkButton(bar, text=text, height=36, corner_radius=18,
                          fg_color=theme.duo("accent" if accent else "panel2"),
                          hover_color=theme.duo("accent_hover" if accent else "hover"),
                          text_color="#04140a" if accent else theme.duo("text"), border_width=0 if accent else 1,
                          border_color=theme.duo("border"), command=cmd).pack(side="left", padx=4, pady=4)
        self.msg = ctk.CTkLabel(bar, text="", text_color=theme.duo("muted"))
        self.msg.pack(side="left", padx=12)

        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list.grid(row=3, column=0, sticky="nsew", padx=18, pady=(6, 16))

    def set_message(self, text: str) -> None:
        self.msg.configure(text=text)

    def refresh(self, rows: list) -> None:
        for child in self.list.winfo_children():
            child.destroy()
        if not rows:
            ctk.CTkLabel(self.list, text="No tool servers yet.\nClick \"Import from Codex\" to bring in REA and "
                         "your other Codex tools.", text_color=theme.duo("muted")).pack(pady=40)
            return
        for r in rows:
            card = ctk.CTkFrame(self.list, corner_radius=16, border_width=1, border_color=theme.duo("border"),
                                fg_color=theme.duo("panel2"))
            card.pack(fill="x", padx=8, pady=5)
            card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text="", image=icons.icon("plug", 22)).grid(row=0, column=0, rowspan=2, padx=16, pady=12)
            ctk.CTkLabel(card, text=r["name"], anchor="w", font=ctk.CTkFont(size=15, weight="bold")
                         ).grid(row=0, column=1, sticky="w", pady=(10, 0))
            label, color = STATUS.get(r["status"], STATUS["idle"])
            detail = f"{label}" + (f" - {r['tools']} tools" if r["status"] == "connected" else "")
            if r["status"] == "error":
                detail += f": {r['error']}"
            ctk.CTkLabel(card, text=detail, anchor="w", text_color=theme.duo(color), wraplength=520, justify="left"
                         ).grid(row=1, column=1, sticky="w")
            ctk.CTkLabel(card, text=r["command"][:90], anchor="w", text_color=theme.duo("muted"),
                         font=ctk.CTkFont(size=11)).grid(row=2, column=1, sticky="w", pady=(0, 10))
            sw = ctk.CTkSwitch(card, text="Enabled", progress_color=theme.duo("accent"), command=lambda n=r["name"]: self.app.mcp_set_enabled(
                n, bool(self._switches[n].get())))
            if not hasattr(self, "_switches"):
                self._switches = {}
            self._switches[r["name"]] = sw
            sw.grid(row=0, column=2, padx=10, pady=(10, 0))
            if r["enabled"]:
                sw.select()
            ctk.CTkButton(card, text="Remove", width=70, height=28, corner_radius=14, fg_color="transparent",
                          hover_color=theme.duo("danger"), text_color=theme.duo("muted"),
                          command=lambda n=r["name"]: self.app.mcp_remove(n)).grid(row=1, column=2, padx=10)

    def _add_dialog(self) -> None:
        win = ctk.CTkToplevel(self)
        win.title("Add tool server")
        win.geometry("460x330")
        win.transient(self.winfo_toplevel())
        win.after(100, win.grab_set)
        fields = {}
        for label, hint in (("Name", "e.g. rea"), ("Command", "e.g. python  /  npx  /  C:\\path\\server.exe"),
                            ("Arguments", "e.g. -m rea_server --stdio")):
            ctk.CTkLabel(win, text=label, anchor="w").pack(fill="x", padx=24, pady=(14, 0))
            entry = ctk.CTkEntry(win, placeholder_text=hint, height=36)
            entry.pack(fill="x", padx=24)
            fields[label] = entry

        def save() -> None:
            name, command = fields["Name"].get().strip(), fields["Command"].get().strip()
            if not name or not command:
                return
            args = shlex.split(fields["Arguments"].get(), posix=sys.platform != "win32")
            win.destroy()
            self.app.mcp_add_server(name, command, args)
        ctk.CTkButton(win, text="Save", height=38, corner_radius=19, fg_color=theme.duo("accent"),
                      hover_color=theme.duo("accent_hover"), text_color="#04140a", command=save
                      ).pack(pady=22, padx=24, fill="x")
