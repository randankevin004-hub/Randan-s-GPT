"""
ui/chat_page.py
---------------
The centre card: header (model pill + menu), a welcome screen with the orb
(or the conversation), and the input box with attach / templates /
Reasoning / Deep Research / mic / send.
"""
from __future__ import annotations

import customtkinter as ctk

from ui import graphics, icons, theme
from ui.chat_view import ChatView
from ui.welcome import WelcomeCanvas
from ui.widgets import Tooltip, icon_button

PLACEHOLDER = "Start your request, and let Randan's handle everything."


class ChatPage(ctk.CTkFrame):
    def __init__(self, master, app, font_size: int = 14) -> None:
        super().__init__(master, corner_radius=24, border_width=1, border_color=theme.duo("border"),
                         fg_color=theme.duo("panel"))
        self.app = app
        self._mode = "welcome"
        self._welcome_geo = (0, 0, 560)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ---- header ---------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        header.grid_columnconfigure(2, weight=1)
        self.model_pill = ctk.CTkButton(
            header, text="", image=graphics.orb_image(26), compound="left", height=40, corner_radius=20,
            fg_color=theme.duo("panel2"), hover_color=theme.duo("hover"), border_width=1,
            border_color=theme.duo("accent"), text_color=theme.duo("text"),
            command=lambda: app.show_model_picker(self.model_pill))
        self.model_pill.grid(row=0, column=0)
        Tooltip(self.model_pill, "Choose model")
        self.mode_chip = ctk.CTkButton(
            header, text="", height=32, corner_radius=16, fg_color=theme.duo("accent_soft"),
            hover_color=theme.duo("hover"), border_width=1, border_color=theme.duo("accent"),
            text_color=theme.duo("accent"), command=lambda: app.select_tool(None))
        self.mode_chip.grid(row=0, column=1, padx=10)
        self.mode_chip.grid_remove()
        self.menu_btn = icon_button(header, "dots", lambda: app.show_chat_menu(self.menu_btn), box=40,
                                    tip="Chat options")
        self.menu_btn.grid(row=0, column=3)

        # ---- content: welcome canvas / conversation ----------------------
        self.welcome = WelcomeCanvas(self, self._on_welcome_layout)
        self.chat_view = ChatView(self, font_size)
        self.welcome.grid(row=1, column=0, sticky="nsew", padx=3)

        self.status = ctk.CTkLabel(self, text="", anchor="w", text_color=theme.duo("muted"),
                                   font=ctk.CTkFont(size=12), wraplength=700, justify="left", height=18)
        self.status.grid(row=2, column=0, padx=24, sticky="ew")

        self._build_input(font_size)
        self.set_mode("welcome")

    # ------------------------------------------------------------ input box
    def _build_input(self, font_size: int) -> None:
        app = self.app
        self.box = ctk.CTkFrame(self, corner_radius=22, border_width=1, border_color=theme.duo("border"),
                                fg_color=theme.duo("panel2"))
        self.box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.box, text="", image=icons.icon("sparkle", 16)).grid(row=0, column=0, padx=(16, 0),
                                                                              pady=(14, 0), sticky="n")
        self.entry = ctk.CTkTextbox(self.box, height=58, wrap="word", border_width=0, fg_color="transparent",
                                    font=ctk.CTkFont(size=font_size))
        self.entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(6, 12), pady=(8, 0))
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<KeyRelease>", lambda e: self._update_placeholder())
        self.placeholder = ctk.CTkLabel(self.box, text=PLACEHOLDER, text_color=theme.duo("muted"),
                                        font=ctk.CTkFont(size=font_size), anchor="w", cursor="xterm")
        self.placeholder.grid(row=0, column=1, columnspan=2, sticky="nw", padx=(14, 12), pady=(15, 0))
        self.placeholder.bind("<Button-1>", lambda e: self.entry.focus_set())

        self.chip = ctk.CTkButton(self.box, text="", height=28, corner_radius=14, fg_color=theme.duo("accent_soft"),
                                  hover_color=theme.duo("hover"), text_color=theme.duo("accent"),
                                  border_width=1, border_color=theme.duo("accent"),
                                  command=app.remove_attachment)
        self.chip.grid(row=1, column=0, columnspan=3, sticky="w", padx=16, pady=(2, 0))
        self.chip.grid_remove()

        bar = ctk.CTkFrame(self.box, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=14, pady=(6, 12))
        bar.grid_columnconfigure(5, weight=1)
        icon_button(bar, "paperclip", app.attach_file, tip="Attach a text / code file").grid(row=0, column=0, padx=3)
        self.notes_btn = icon_button(bar, "note", None, tip="Prompt templates")
        self.notes_btn.configure(command=lambda: app.show_templates(self.notes_btn))
        self.notes_btn.grid(row=0, column=1, padx=3)
        self.reason_btn = self._pill(bar, "bulb", "Reasoning", app.toggle_reasoning,
                                     "Think step by step with DeepSeek R1")
        self.reason_btn.grid(row=0, column=2, padx=3)
        self.research_btn = self._pill(bar, "research", "Deep Research", app.toggle_research,
                                       "Long, structured report-style answers")
        self.research_btn.grid(row=0, column=3, padx=3)
        self.tools_btn = self._pill(bar, "plug", "Tools", app.toggle_tools,
                                    "Let the model use your MCP tool servers (e.g. REA)")
        self.tools_btn.grid(row=0, column=4, padx=3)
        icon_button(bar, "mic", app.start_voice, tip="Voice typing").grid(row=0, column=6, padx=3)
        self.send_img, self.stop_img = graphics.send_button_image(42), graphics.send_button_image(42, stop=True)
        self.send_btn = ctk.CTkButton(bar, text="", image=self.send_img, width=42, height=42, corner_radius=21,
                                      fg_color="transparent", hover_color=theme.duo("panel2"),
                                      command=app.send_or_stop)
        self.send_btn.grid(row=0, column=7, padx=(3, 0))
        Tooltip(self.send_btn, "Send  (Enter)")

    def _pill(self, master, icon_name, text, command, tip):
        btn = ctk.CTkButton(master, text=" " + text, image=icons.icon(icon_name, 16), compound="left", height=38,
                            corner_radius=19, fg_color=theme.duo("panel2"), hover_color=theme.duo("hover"),
                            border_width=1, border_color=theme.duo("border"), text_color=theme.duo("text"),
                            command=command)
        Tooltip(btn, tip)
        return btn

    # ---------------------------------------------------------------- modes
    def _on_welcome_layout(self, cx: float, top: float, width: int) -> None:
        self._welcome_geo = (cx, top, width)
        if self._mode == "welcome":
            self.box.configure(width=width)
            self.box.place(in_=self.welcome, x=cx, y=top, anchor="n")
            self.box.lift()

    def set_mode(self, mode: str) -> None:
        """'welcome' = orb + centred input; 'chat' = conversation + bottom input."""
        self._mode = mode
        if mode == "welcome":
            self.chat_view.grid_remove()
            self.welcome.grid()
            cx, top, width = self._welcome_geo
            self.box.grid_remove()
            self.box.configure(width=width)
            self.box.place(in_=self.welcome, x=cx or 300, y=top or 300, anchor="n")
            self.box.lift()
        else:
            self.welcome.grid_remove()
            self.box.place_forget()
            self.chat_view.grid(row=1, column=0, sticky="nsew", padx=3)
            self.box.grid(row=3, column=0, sticky="ew", padx=22, pady=(4, 18))

    @property
    def mode(self) -> str:
        return self._mode

    def refresh_theme(self) -> None:
        self.welcome.refresh_theme()
        self.model_pill.configure(image=graphics.orb_image(26))

    # ------------------------------------------------------------------ API
    def _on_enter(self, event):
        if event.state & 0x0001:          # Shift -> newline
            return None
        self.app.send_or_stop()
        return "break"

    def _update_placeholder(self) -> None:
        if self.entry.get("1.0", "end-1c"):
            self.placeholder.grid_remove()
        else:
            self.placeholder.grid()

    def get_text(self) -> str:
        return self.entry.get("1.0", "end-1c")

    def clear_input(self) -> None:
        self.entry.delete("1.0", "end")
        self._update_placeholder()

    def insert_text(self, text: str) -> None:
        self.entry.insert("end", text)
        self._update_placeholder()
        self.entry.focus_set()

    def focus_input(self) -> None:
        self.entry.focus_set()

    def set_greeting(self, text: str) -> None:
        self.welcome.set_greeting(text)

    def set_model_label(self, text: str) -> None:
        self.model_pill.configure(text="  " + text + "   \u25BE")

    def set_mode_chip(self, text: str | None) -> None:
        if text:
            self.mode_chip.configure(text=f"{text}  \u2715")
            self.mode_chip.grid()
        else:
            self.mode_chip.grid_remove()

    def set_toggle(self, which: str, on: bool) -> None:
        btn = {"reasoning": self.reason_btn, "research": self.research_btn, "tools": self.tools_btn}[which]
        btn.configure(border_color=theme.duo("accent") if on else theme.duo("border"),
                      fg_color=theme.duo("accent_soft") if on else theme.duo("panel2"),
                      text_color=theme.duo("accent") if on else theme.duo("text"))

    def set_attachment(self, name: str | None) -> None:
        if name:
            self.chip.configure(text=f"  {name}   \u2715", image=icons.icon("paperclip", 14))
            self.chip.grid()
        else:
            self.chip.grid_remove()

    def set_generating(self, busy: bool) -> None:
        self.send_btn.configure(image=self.stop_img if busy else self.send_img)

    def show_status(self, text: str, error: bool = False) -> None:
        self.status.configure(text=text, text_color=theme.duo("danger" if error else "muted"))

    def set_font_size(self, size: int) -> None:
        font = ctk.CTkFont(size=size)
        self.entry.configure(font=font)
        self.placeholder.configure(font=font)
        self.chat_view.font_size = size
