"""ui/help_page.py - quick start, shortcuts, tool guide, FAQ and About."""
from __future__ import annotations

import os
import sys
import webbrowser

import customtkinter as ctk

from settings.config import APP_NAME, APP_VERSION, app_data_dir
from ui import graphics, theme

SECTIONS = [
    ("Getting started", "1. Make sure the Ollama app is running (look for 'Ollama online' on the Dashboard).\n"
     "2. Pick a model from the pill at the top of the chat, or choose Auto to let the app decide.\n"
     "3. Type your request and press Enter (Shift+Enter adds a new line)."),
    ("Keyboard shortcuts", "Enter - send  |  Shift+Enter - new line  |  Ctrl+N - new chat  |  Esc - stop / close menus"),
    ("Chat tools", "The round icons on the left switch the assistant's role and model: Code, Math, Writing, "
     "Translator, Summarizer, Brainstorm (+ more under the arrow). Click the active one again to switch it off.\n"
     "Reasoning = step-by-step thinking with DeepSeek R1.  Deep Research = long, structured, report-style answers "
     "(runs fully offline - it does not browse the web).\n"
     "Paperclip attaches a text or code file.  The note icon inserts prompt templates.  The mic starts Windows voice typing (Win+H)."),
    ("Tools (MCP / REA)", "Open Settings > Tool servers > Manage, click 'Import from Codex' to bring in REA and your other "
     "Codex tools, then switch on the Tools button in the chat. The model picks relevant tools for each question and "
     "asks your permission before running them. Use a tool-capable model (Qwen 2.5, Qwen3.5, Llama 3.2)."),
    ("Memory", "Say 'Remember that I'm building Podchain.' to save a fact, 'What do you know about me?' to list "
     "them, or 'Forget everything' to clear them. Manage memories in Settings."),
    ("Troubleshooting", "'Can't reach Ollama' - start the Ollama app or run `ollama serve`.\n"
     "'Model isn't installed' - run `ollama pull <model>` in a terminal.\n"
     "Slow replies - use a smaller model (Llama 3.2 1B) and lower the context size in settings.json."),
]


class HelpPage(ctk.CTkScrollableFrame):
    def __init__(self, master) -> None:
        super().__init__(master, corner_radius=24, border_width=1, border_color=theme.duo("border"),
                         fg_color=theme.duo("panel"))
        ctk.CTkLabel(self, text="Help", font=ctk.CTkFont(size=26, weight="bold"), anchor="w"
                     ).pack(fill="x", padx=24, pady=(20, 8))
        for title, body in SECTIONS:
            card = ctk.CTkFrame(self, corner_radius=16, border_width=1, border_color=theme.duo("border"),
                                fg_color=theme.duo("panel2"))
            card.pack(fill="x", padx=20, pady=6)
            ctk.CTkLabel(card, text=title, anchor="w", font=ctk.CTkFont(size=15, weight="bold"),
                         text_color=theme.duo("accent")).pack(fill="x", padx=16, pady=(12, 2))
            ctk.CTkLabel(card, text=body, anchor="w", justify="left", wraplength=760).pack(fill="x", padx=16, pady=(0, 12))

        about = ctk.CTkFrame(self, corner_radius=16, border_width=1, border_color=theme.duo("border"),
                             fg_color=theme.duo("panel2"))
        about.pack(fill="x", padx=20, pady=(6, 20))
        ctk.CTkLabel(about, text="", image=graphics.orb_image(54)).pack(pady=(14, 0))
        ctk.CTkLabel(about, text=APP_NAME, font=ctk.CTkFont(size=22, weight="bold")).pack()
        ctk.CTkLabel(about, text=f"Version {APP_VERSION}", text_color=theme.duo("muted")).pack()
        ctk.CTkLabel(about, text="Powered by:  Ollama  \u2022  Llama  \u2022  Gemma  \u2022  DeepSeek  \u2022  Qwen",
                     pady=8).pack()
        row = ctk.CTkFrame(about, fg_color="transparent")
        row.pack(pady=(0, 14))
        for text, cmd in (("Open Ollama website", lambda: webbrowser.open("https://ollama.com")),
                          ("Open data folder", self._open_data)):
            ctk.CTkButton(row, text=text, height=34, corner_radius=17, fg_color=theme.duo("accent_soft"),
                          hover_color=theme.duo("hover"), border_width=1, border_color=theme.duo("accent"),
                          text_color=theme.duo("accent"), command=cmd).pack(side="left", padx=6)

    @staticmethod
    def _open_data() -> None:
        path = str(app_data_dir())
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        else:
            webbrowser.open("file://" + path)
