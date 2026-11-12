"""
ui/settings_page.py
-------------------
Settings: default model, start-in-Auto, theme, font size, memory on/off and
a small manager for saved memories. Changes apply immediately.
"""
from __future__ import annotations

import customtkinter as ctk

from settings.config import Settings
from ui import theme

FONT_SIZES = ["12", "13", "14", "15", "16", "18", "20"]


class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, master, settings: Settings, on_change, on_delete_memory, on_clear_memories,
                 on_manage_tools=None) -> None:
        super().__init__(master, corner_radius=24, border_width=1, border_color=theme.duo("border"),
                         fg_color=theme.duo("panel"))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._on_delete_memory = on_delete_memory

        ctk.CTkLabel(self, text="Settings", font=ctk.CTkFont(size=26, weight="bold"),
                     anchor="w").grid(row=0, column=0, padx=30, pady=(24, 10), sticky="w")

        card = ctk.CTkFrame(self, fg_color=theme.duo("panel2"), corner_radius=18, border_width=1,
                            border_color=theme.duo("border"))
        card.grid(row=1, column=0, padx=30, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        def row(i: int, title: str, subtitle: str) -> None:
            box = ctk.CTkFrame(card, fg_color="transparent")
            box.grid(row=i, column=0, padx=20, pady=8, sticky="w")
            ctk.CTkLabel(box, text=title, anchor="w", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(box, text=subtitle, anchor="w", text_color=theme.duo("muted"),
                         font=ctk.CTkFont(size=12)).pack(anchor="w")

        # Default model
        row(0, "Default model", "Model used when you start a chat")
        self.model_menu = ctk.CTkOptionMenu(
            card, values=["Llama 3.2 1B"], width=250,
            command=lambda label: on_change("default_model", label))
        self.model_menu.grid(row=0, column=1, padx=20)

        # Start in Auto mode
        row(1, "Start in Auto mode", "Automatically pick the best model for each question")
        self.auto_switch = ctk.CTkSwitch(card, text="", progress_color=theme.duo("accent"), command=lambda: on_change(
            "auto_mode", bool(self.auto_switch.get())))
        self.auto_switch.grid(row=1, column=1, padx=20)
        if settings.get("auto_mode"):
            self.auto_switch.select()

        # Theme
        row(2, "Theme", "Dark or light appearance")
        self.theme_btn = ctk.CTkSegmentedButton(
            card, values=["Dark", "Light"], command=lambda v: on_change("theme", v))
        self.theme_btn.set(settings.get("theme"))
        self.theme_btn.grid(row=2, column=1, padx=20)

        # Font size
        row(3, "Font size", "Chat text size")
        self.font_menu = ctk.CTkOptionMenu(
            card, values=FONT_SIZES, width=80,
            command=lambda v: on_change("font_size", int(v)))
        self.font_menu.set(str(settings.get("font_size")))
        self.font_menu.grid(row=3, column=1, padx=20)

        # Memory on/off
        row(4, "Memory", "Remember facts you ask it to (\"Remember that ...\")")
        self.memory_switch = ctk.CTkSwitch(card, text="", progress_color=theme.duo("accent"), command=lambda: on_change(
            "memory_enabled", bool(self.memory_switch.get())))
        self.memory_switch.grid(row=4, column=1, padx=20)
        if settings.get("memory_enabled"):
            self.memory_switch.select()

        # MCP tools
        row(5, "Tool servers (MCP)", "Connect tools such as REA, imported from Codex")
        ctk.CTkButton(card, text="Manage...", width=110, height=32, corner_radius=16,
                      fg_color=theme.duo("accent_soft"), hover_color=theme.duo("hover"), border_width=1,
                      border_color=theme.duo("accent"), text_color=theme.duo("accent"),
                      command=on_manage_tools).grid(row=5, column=1, padx=20)
        row(6, "Ask before running tools", "Show a confirmation each time the model wants to run a tool")
        self.confirm_switch = ctk.CTkSwitch(card, text="", progress_color=theme.duo("accent"), command=lambda: on_change(
            "mcp_confirm", bool(self.confirm_switch.get())))
        self.confirm_switch.grid(row=6, column=1, padx=20)
        if settings.get("mcp_confirm"):
            self.confirm_switch.select()

        # Saved memories
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=2, column=0, padx=30, pady=(18, 0), sticky="new")
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Saved memories", font=ctk.CTkFont(size=16, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(head, text="Clear all", width=90, height=28, fg_color=theme.duo("danger"),
                      hover_color=("#b3292e", "#b3292e"), text_color="#ffffff",
                      command=on_clear_memories).grid(row=0, column=1)
        self.memory_list = ctk.CTkScrollableFrame(head, height=110, fg_color=theme.duo("panel2"))
        self.memory_list.grid(row=1, column=0, columnspan=2, pady=(8, 0), sticky="ew")

    def set_models(self, labels: list, current: str) -> None:
        """Fill the Default-model dropdown with every available model."""
        self.model_menu.configure(values=labels)
        self.model_menu.set(current)

    def refresh_memories(self, memories: list) -> None:
        for child in self.memory_list.winfo_children():
            child.destroy()
        if not memories:
            ctk.CTkLabel(self.memory_list, text="Nothing saved yet.",
                         text_color=theme.duo("muted")).pack(pady=10)
            return
        for item in memories:
            line = ctk.CTkFrame(self.memory_list, fg_color="transparent")
            line.pack(fill="x", pady=2)
            ctk.CTkButton(
                line, text="\u2715", width=26, height=26, fg_color="transparent",
                hover_color=theme.duo("danger"), text_color=theme.duo("muted"),
                command=lambda mid=item["id"]: self._on_delete_memory(mid),
            ).pack(side="right")
            ctk.CTkLabel(line, text=item["content"], anchor="w", justify="left",
                         wraplength=640).pack(side="left", fill="x", expand=True, padx=6)
