"""
ui/app.py
---------
Main window and application controller. It wires the UI to the services:

    Settings  -> settings/config.py        MemoryManager -> memory/
    Database  -> database/db.py            OllamaService -> models/

Threading model
~~~~~~~~~~~~~~~
Only the Tk main thread touches widgets. Generation runs in a worker thread
that pushes (generation_id, kind, payload) tuples into `self._events`; a pump
running every 40 ms on the main thread drains the queue, so the UI never
freezes and text appears live, token by token.
"""
from __future__ import annotations

import json
import logging
import queue
import re
import sys
import threading
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from backend.prompts import (REASONING_MODEL, REASONING_PROMPT, RESEARCH_PROMPT, SYSTEM_PROMPT,
                             MAX_ATTACH_CHARS, display_text, model_text)
from database.db import Database
from memory.memory_manager import MemoryManager
from models.mcp_client import McpManager, import_codex_servers, load_config, save_config
from models.ollama_client import OllamaError, OllamaService, clean_for_model
from models.router import (AUTO_LABEL, DEFAULT_MODEL, GENERAL_MODEL, MODELS, WRITING_MODEL,
                           label_for, route)
from settings.config import APP_NAME, Settings, app_data_dir, resource_path
from ui import graphics, theme
from ui.account_page import AccountPage
from ui.chat_page import ChatPage
from ui.dashboard_page import DashboardPage
from ui.export import export_pdf, export_txt
from ui.help_page import HelpPage
from ui.history_panel import HistoryPanel
from ui.navbar import NAV, NavBar
from ui.rail import ToolRail
from ui.settings_page import SettingsPage
from ui.tools_page import ToolsPage
from ui.tools import ALL_TOOLS, MORE_TOOLS, TEMPLATES
from ui.widgets import Popover, add_menu_items

class App(ctk.CTk):
    def __init__(self) -> None:
        settings = Settings()
        if not settings.get("member_since"):
            settings.set("member_since", datetime.now().strftime("%b %Y"))
        theme.set_theme(settings.get("theme"))     # must happen before widgets exist
        super().__init__(fg_color=theme.duo("bg"))

        # ---- services -------------------------------------------------
        self.settings = settings
        self.db = Database()
        self.memory = MemoryManager(self.db)
        self.ollama = OllamaService()
        self.mcp = McpManager()
        self._mcp_cfg: dict = load_config()

        # ---- state ----------------------------------------------------
        self.current_chat_id: int | None = None
        saved = settings.get("default_model")
        self.current_model = saved or DEFAULT_MODEL
        self._tags: list = []
        self._label_to_tag: dict = {}
        self.auto_mode = bool(settings.get("auto_mode"))
        self.active_tool: str | None = None
        self.reasoning = False
        self.research = False
        self.tools_on = False
        self._dialog_open = False
        self.page = "chat"
        self._attachment: tuple | None = None
        self._notifications: list = []
        self._online: bool | None = None
        self._installed: list = []
        self._generating = False
        self._gen_id = 0
        self._stop_event: threading.Event | None = None
        self._events: queue.Queue = queue.Queue()
        self._buffer = ""
        self._bubble = None
        self._model_in_use = ""

        self.title(APP_NAME)
        self.geometry("1280x780")
        self.minsize(1000, 640)
        self.after(250, self._set_icon)      # CTk overrides icons; set after it
        self._build_ui()
        self.bind("<Control-n>", lambda e: self.new_chat())
        self.bind("<Escape>", lambda e: self.stop_generation() if self._generating and Popover._current is None else None)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.navbar.set_theme_buttons(theme.current_name())
        self._refresh_avatar()
        self._refresh_models()
        self._sync_model_ui()
        self.refresh_history()
        self.new_chat()
        self.notify("Welcome to Randan's GPT",
                    'Tip: say "Remember that ..." and I\'ll keep it in memory. Pick a tool on the left to change my role.')
        self._check_ollama_async()
        self._pump()

    # ================================================================= UI
    def _set_icon(self) -> None:
        try:
            self.iconbitmap(resource_path("assets/icon.ico"))
        except Exception:  # noqa: BLE001 - icon is cosmetic only
            pass

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.navbar = NavBar(self, on_nav=self.show_page, on_theme=self.apply_theme,
                             on_history=self.toggle_history, on_bell=self.show_notifications,
                             on_avatar=lambda: self.show_page("account"))
        self.navbar.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(4, 14))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.rail = ToolRail(body, on_tool=self.select_tool, on_more=self.show_more_tools,
                             on_settings=lambda: self.show_page("settings"), on_logout=self.logout)
        self.rail.grid(row=0, column=0, sticky="ns", padx=(0, 6))

        host = ctk.CTkFrame(body, fg_color="transparent")
        host.grid(row=0, column=1, sticky="nsew", padx=6)
        host.grid_columnconfigure(0, weight=1)
        host.grid_rowconfigure(0, weight=1)
        self.chat_page = ChatPage(host, self, int(self.settings.get("font_size")))
        self.dashboard = DashboardPage(host, self)
        self.help_page = HelpPage(host)
        self.account = AccountPage(host, self)
        self.settings_page = SettingsPage(
            host, self.settings, on_change=self.on_setting_changed,
            on_delete_memory=self.delete_memory, on_clear_memories=self.clear_memories,
            on_manage_tools=lambda: self.show_page("tools"))
        self.tools_page = ToolsPage(host, self)
        self.pages = {"chat": self.chat_page, "dashboard": self.dashboard, "help": self.help_page,
                      "account": self.account, "settings": self.settings_page, "tools": self.tools_page}
        for frame in self.pages.values():          # stacked; the active one is raised
            frame.grid(row=0, column=0, sticky="nsew")
        self.chat_view = self.chat_page.chat_view

        self.history = HistoryPanel(body, on_new=self.new_chat, on_select=self.open_chat,
                                    on_menu=self.show_history_menu)
        self.history.grid(row=0, column=2, sticky="ns", padx=(6, 0))
        self.show_page("chat")

    def show_page(self, name: str) -> None:
        Popover.close_current()
        self.page = name
        if name == "settings":
            self.settings_page.refresh_memories(self.db.list_memories())
        elif name == "tools":
            self.mcp_refresh_ui()
        elif name == "dashboard":
            self.dashboard.refresh(self.db.stats(), bool(self._online), self._installed)
        elif name == "account":
            self.account.refresh(self.settings.get("user_name"), self.settings.get("avatar_path"),
                                 self.db.stats(), self.settings.get("member_since"))
        page = self.pages[name]
        getattr(page, "_parent_frame", page).tkraise()   # scrollable pages live in an outer frame
        self.navbar.set_active(name if name in dict(NAV) else None)
        self._update_history_visibility()
        if name == "chat":
            self.chat_page.focus_input()

    def _update_history_visibility(self) -> None:
        if self.page == "chat" and self.settings.get("show_history"):
            self.history.grid()
        else:
            self.history.grid_remove()

    def toggle_history(self) -> None:
        self.settings.set("show_history", not self.settings.get("show_history"))
        if self.page != "chat":
            self.show_page("chat")
        else:
            self._update_history_visibility()

    # ============================================================== theme
    def apply_theme(self, mode: str) -> None:
        self.settings.set("theme", mode)
        theme.set_theme(mode)
        self.configure(fg_color=theme.duo("bg"))
        self.navbar.set_theme_buttons(mode)
        self.settings_page.theme_btn.set(mode)
        self.chat_page.refresh_theme()
        self._reload_current_chat()
        self.refresh_history()
        if self.page == "dashboard":
            self.show_page("dashboard")

    # ============================================================== models
    def _refresh_models(self) -> None:
        """Rebuild the model list: installed Ollama models (or defaults/known ones offline)."""
        base = [m.tag for m in MODELS]
        if self._online and self._installed:
            tags = [t for t in base if t in self._installed or f"{t}:latest" in self._installed]
            tags += [t for t in self._installed if t not in tags and not t.endswith(":latest")]
            tags = tags or base
        else:
            tags = base + [t for t in self.settings.get("known_models") if t not in base]
        if self.current_model not in tags:
            tags.append(self.current_model)
        self._tags = tags
        self._label_to_tag = {label_for(t): t for t in tags}
        self.settings_page.set_models([label_for(t) for t in tags], label_for(self.current_model))

    def on_model_selected(self, label: str) -> None:
        """The chosen model becomes active immediately."""
        if label == AUTO_LABEL:
            self.auto_mode = True
        else:
            self.auto_mode = False
            self.current_model = self._label_to_tag.get(label, label)
        self.reasoning = False
        self.chat_page.set_toggle("reasoning", False)
        self._sync_model_ui()

    def show_model_picker(self, anchor) -> None:
        def build(pop, close):
            items = [(AUTO_LABEL, "sparkle", lambda: self.on_model_selected(AUTO_LABEL),
                      {"checked": self.auto_mode and not self.reasoning})]
            for tag in self._tags:
                checked = (not self.auto_mode and not self.reasoning and tag == self.current_model)
                items.append((label_for(tag), None, lambda t=tag: self.on_model_selected(label_for(t)),
                              {"checked": checked}))
            add_menu_items(pop, items, close)
        Popover.show(anchor, build, width=300)

    def _sync_model_ui(self) -> None:
        if self._generating:
            name = label_for(self._model_in_use)
            label = f"Auto \u2192 {name}" if self.auto_mode else name
        elif self.reasoning:
            label = label_for(REASONING_MODEL) + " (Reasoning)"
        elif self.auto_mode:
            label = "Auto"
        else:
            label = label_for(self.current_model)
        self.chat_page.set_model_label(label)

    def _resolve_model(self, text: str) -> str:
        if self.reasoning:
            return REASONING_MODEL
        if self.auto_mode:
            model = route(text)
            return WRITING_MODEL if (self.research and model == GENERAL_MODEL) else model
        return self.current_model

    # ============================================================== tools
    def select_tool(self, key: str | None) -> None:
        """Rail button: switch persona + preferred model (click again to clear)."""
        if key == self.active_tool:
            key = None
        self.active_tool = key
        self.rail.set_active(key)
        tool = ALL_TOOLS.get(key) if key else None
        if tool:
            self.current_model, self.auto_mode, self.reasoning = tool.model, False, False
            self.chat_page.set_toggle("reasoning", False)
        self.chat_page.set_mode_chip(tool.label if tool else None)
        self._sync_model_ui()
        if self.page != "chat":
            self.show_page("chat")
        self.chat_page.show_status(f"{tool.label} mode on - using {label_for(tool.model)}." if tool else "")
        self.chat_page.focus_input()

    def show_more_tools(self, anchor) -> None:
        def build(pop, close):
            add_menu_items(pop, [(t.label, t.icon, lambda k=t.key: self.select_tool(k),
                                  {"checked": t.key == self.active_tool}) for t in MORE_TOOLS], close)
        Popover.show(anchor, build, width=220, side="right")

    def toggle_reasoning(self) -> None:
        self.reasoning = not self.reasoning
        self.chat_page.set_toggle("reasoning", self.reasoning)
        self._sync_model_ui()
        self.chat_page.show_status("Reasoning on - DeepSeek R1 will think step by step." if self.reasoning else "")

    def toggle_research(self) -> None:
        self.research = not self.research
        self.chat_page.set_toggle("research", self.research)
        self.chat_page.show_status("Deep Research on - long, structured answers (offline, no web browsing)."
                                   if self.research else "")

    # ===================================================== MCP tool servers
    def toggle_tools(self) -> None:
        self.tools_on = not self.tools_on
        self.chat_page.set_toggle("tools", self.tools_on)
        if not self.tools_on:
            self.chat_page.show_status("")
            return
        if not self._mcp_cfg:
            self.chat_page.show_status("No tool servers yet - import them from Codex on the Tools page.", error=True)
            self.show_page("tools")
        elif not self.mcp.has_connected():
            self.mcp_connect_all()
            self.chat_page.show_status("Tools on - connecting your tool servers...")
        else:
            self.chat_page.show_status("Tools on - the model can use your tool servers (you'll be asked first).")

    def mcp_refresh_ui(self) -> None:
        self.tools_page.refresh(self.mcp.snapshot(self._mcp_cfg))

    def mcp_import_codex(self) -> None:
        try:
            found = import_codex_servers()
        except FileNotFoundError as exc:
            self.tools_page.set_message(f"Codex config not found: {exc}")
            return
        except Exception as exc:  # noqa: BLE001
            self.tools_page.set_message(f"Couldn't read Codex config: {exc}")
            return
        new = [n for n in found if n not in self._mcp_cfg]
        for name in new:
            self._mcp_cfg[name] = found[name]
        save_config(self._mcp_cfg)
        self.tools_page.set_message(f"Imported {len(new)} new server(s): {', '.join(new) or 'none - already added'}")
        self.mcp_refresh_ui()
        if new:
            self.mcp_connect_all()

    def mcp_add_server(self, name: str, command: str, args: list) -> None:
        self._mcp_cfg[name] = {"command": command, "args": args, "enabled": True}
        save_config(self._mcp_cfg)
        self.mcp_connect_all()

    def mcp_remove(self, name: str) -> None:
        self._mcp_cfg.pop(name, None)
        save_config(self._mcp_cfg)
        threading.Thread(target=self.mcp.disconnect, args=(name,), daemon=True).start()
        self.mcp_refresh_ui()

    def mcp_set_enabled(self, name: str, on: bool) -> None:
        if name in self._mcp_cfg:
            self._mcp_cfg[name]["enabled"] = on
            save_config(self._mcp_cfg)
            if on:
                self.mcp_connect_all()
            else:
                threading.Thread(target=self.mcp.disconnect, args=(name,), daemon=True).start()
                self.mcp_refresh_ui()

    def mcp_connect_all(self) -> None:
        """Connect every enabled server in the background (UI stays responsive)."""
        todo = {n: c for n, c in self._mcp_cfg.items() if c.get("enabled", True)}
        if not todo:
            self.tools_page.set_message("Nothing to connect - add or enable a server first.")
            return

        def work() -> None:
            for name, cfg in todo.items():
                self._events.put((0, "mcp", f"Connecting {name}..."))
                try:
                    self.mcp.connect(name, cfg)
                except Exception as exc:  # noqa: BLE001
                    logging.warning("MCP connect failed for %s: %s", name, exc)
                self._events.put((0, "mcp", ""))
        self.tools_page.set_message("Connecting...")
        threading.Thread(target=work, daemon=True).start()

    def _run_tool(self, gen_id: int, stop_event: threading.Event, alias: str, args: dict) -> str:
        """Called from the worker thread when the model asks for a tool."""
        if self.settings.get("mcp_confirm"):
            reply: queue.Queue = queue.Queue()
            self._events.put((gen_id, "approve", (alias, args, reply)))
            allowed = None
            while allowed is None and not stop_event.is_set():
                try:
                    allowed = reply.get(timeout=0.2)
                except queue.Empty:
                    pass
            if not allowed:
                return "The user did not allow this tool to run."
        try:
            out = self.mcp.call_alias(alias, args)
        except Exception as exc:  # noqa: BLE001
            return f"Error: {exc}"
        return out if len(out) <= 6000 else out[:6000] + "\n...[output truncated]"

    def _ask_approval(self, alias: str, args: dict, reply: "queue.Queue") -> None:
        """Main thread: confirmation dialog before a tool runs."""
        shown = json.dumps(args, indent=2, ensure_ascii=False)
        self._dialog_open = True
        try:
            ok = messagebox.askyesno(
                "Allow tool?", f"The model wants to run:\n\n  {self.mcp.describe(alias)}\n\n"
                f"with arguments:\n{shown[:600]}\n\nAllow it?")
        finally:
            self._dialog_open = False
        reply.put(bool(ok))

    # ============================================== attach / templates / mic
    def attach_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Attach a text or code file",
            filetypes=[("Text & code", "*.txt *.md *.py *.js *.ts *.html *.css *.json *.csv *.xml *.log "
                                       "*.java *.c *.cpp *.cs *.kt *.sql *.yml *.yaml *.ini"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                raw = fh.read(2_000_000)
            if b"\x00" in raw[:4096]:
                raise ValueError("That doesn't look like a text file.")
            text = raw.decode("utf-8", errors="replace")
        except (OSError, ValueError) as exc:
            self.chat_page.show_status(f"Couldn't attach the file: {exc}", error=True)
            return
        note = ""
        if len(text) > MAX_ATTACH_CHARS:
            text, note = text[:MAX_ATTACH_CHARS], f" (truncated to {MAX_ATTACH_CHARS:,} characters)"
        name = path.replace("\\", "/").split("/")[-1]
        self._attachment = (name, text)
        self.chat_page.set_attachment(name)
        self.chat_page.show_status(f"Attached {name}{note}. Click the chip to remove it.")

    def remove_attachment(self) -> None:
        self._attachment = None
        self.chat_page.set_attachment(None)
        self.chat_page.show_status("")

    def show_templates(self, anchor) -> None:
        def build(pop, close):
            add_menu_items(pop, [(label, "note", lambda t=text: self.chat_page.insert_text(t))
                                 for label, text in TEMPLATES], close, width=240)
        Popover.show(anchor, build, width=260)

    def start_voice(self) -> None:
        """Opens Windows voice typing (Win+H) in the message box."""
        if sys.platform != "win32":
            self.chat_page.show_status("Voice typing uses Windows' built-in dictation (Win+H) - Windows only.", error=True)
            return
        import ctypes
        self.chat_page.focus_input()
        self.chat_page.show_status("Listening... speak now (Windows voice typing). Press Win+H again to stop.")

        def press() -> None:
            k = ctypes.windll.user32.keybd_event
            k(0x5B, 0, 0, 0); k(0x48, 0, 0, 0); k(0x48, 0, 2, 0); k(0x5B, 0, 2, 0)  # noqa: E702
        self.after(150, press)

    # ======================================================== notifications
    def notify(self, title: str, body: str) -> None:
        self._notifications.insert(0, {"title": title, "body": body,
                                       "time": datetime.now().strftime("%H:%M"), "read": False})
        self._notifications = self._notifications[:30]
        self.navbar.set_unread(sum(not n["read"] for n in self._notifications))

    def show_notifications(self) -> None:
        def build(pop, close):
            head = ctk.CTkFrame(pop, fg_color="transparent")
            head.pack(fill="x", padx=14, pady=(12, 4))
            ctk.CTkLabel(head, text="Notifications", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left")
            ctk.CTkButton(head, text="Clear", width=54, height=24, corner_radius=12, fg_color="transparent",
                          hover_color=theme.duo("hover"), text_color=theme.duo("muted"),
                          command=lambda: (self._notifications.clear(), close(),
                                           self.navbar.set_unread(0))).pack(side="right")
            if not self._notifications:
                ctk.CTkLabel(pop, text="You're all caught up.", text_color=theme.duo("muted")).pack(pady=18, padx=30)
            for n in self._notifications[:8]:
                card = ctk.CTkFrame(pop, corner_radius=12, fg_color=theme.duo("accent_soft" if not n["read"] else "panel"))
                card.pack(fill="x", padx=10, pady=3)
                ctk.CTkLabel(card, text=f"{n['title']}   {n['time']}", anchor="w",
                             font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", padx=10, pady=(6, 0))
                ctk.CTkLabel(card, text=n["body"], anchor="w", justify="left", wraplength=290,
                             text_color=theme.duo("muted"), font=ctk.CTkFont(size=12)).pack(fill="x", padx=10, pady=(0, 6))
            ctk.CTkFrame(pop, height=6, fg_color="transparent").pack()
        Popover.show(self.navbar.bell, build, width=330, align="right")
        for n in self._notifications:
            n["read"] = True
        self.navbar.set_unread(0)

    # ================================================================ profile
    def set_user_name(self, name: str) -> None:
        name = " ".join(name.split())[:30] or "Friend"
        self.settings.set("user_name", name)
        self._refresh_avatar()
        self.chat_page.set_greeting(self._greeting())

    def _refresh_avatar(self) -> None:
        name, path = self.settings.get("user_name"), self.settings.get("avatar_path")
        self.navbar.set_avatar(graphics.avatar_image(path, name, 38))
        if self.page == "account":
            self.account.refresh(name, path, self.db.stats(), self.settings.get("member_since"))

    def change_avatar(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a profile picture",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("All files", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path).convert("RGB")
            side = min(img.size)
            left, top = (img.width - side) // 2, (img.height - side) // 2
            img = img.crop((left, top, left + side, top + side)).resize((256, 256), Image.LANCZOS)
            dest = app_data_dir() / "avatar.png"
            img.save(dest)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(APP_NAME, f"Couldn't use that image:\n{exc}")
            return
        self.settings.set("avatar_path", str(dest))
        self._refresh_avatar()

    def remove_avatar(self) -> None:
        self.settings.set("avatar_path", "")
        self._refresh_avatar()

    def logout(self) -> None:
        if messagebox.askyesno(APP_NAME, "Log out and close Randan's GPT?"):
            self._on_close()

    @staticmethod
    def _greeting_prefix() -> str:
        hour = datetime.now().hour
        return "Good Morning" if hour < 12 else "Good Afternoon" if hour < 17 else "Good Evening"

    def _greeting(self) -> str:
        return f"{self._greeting_prefix()}, {self.settings.get('user_name')}! How can I assist you?"

    # ================================================================ chats
    def refresh_history(self) -> None:
        self.history.refresh(self.db.list_chats(), self.current_chat_id)

    def _busy_notice(self) -> bool:
        if self._generating:
            self.chat_page.show_status("Please wait for the current reply to finish (or press Stop) first.")
        return self._generating

    def new_chat(self) -> None:
        if self._busy_notice():
            return
        self.current_chat_id = None
        self.chat_view.clear()
        self.chat_page.set_mode("welcome")
        self.chat_page.set_greeting(self._greeting())
        self.chat_page.show_status("")
        self.refresh_history()
        self.show_page("chat")

    def open_chat(self, chat_id: int) -> None:
        if self._busy_notice():
            return
        self.current_chat_id = chat_id
        self._load_chat(chat_id)
        self.chat_page.show_status("")
        self.refresh_history()
        self.show_page("chat")

    def _load_chat(self, chat_id: int) -> None:
        self.chat_view.clear()
        messages = self.db.get_messages(chat_id)
        self.chat_page.set_mode("chat" if messages else "welcome")
        for m in messages:
            text = display_text(m["content"]) if m["role"] == "user" else m["content"]
            self.chat_view.add_message(m["role"], text, model=m["model"])
        self.chat_view.scroll_to_bottom(settle=True)

    def _reload_current_chat(self) -> None:
        """Rebuild the conversation (after a theme / font change)."""
        if self._generating:
            return
        if self.current_chat_id is None:
            self.chat_view.clear()
            self.chat_page.set_mode("welcome")
        else:
            self._load_chat(self.current_chat_id)

    def delete_chat(self, chat_id: int) -> None:
        if self._busy_notice():
            return
        if not messagebox.askyesno(APP_NAME, "Delete this chat permanently?"):
            return
        self.db.delete_chat(chat_id)
        if chat_id == self.current_chat_id:
            self.new_chat()
        self.refresh_history()

    def rename_chat(self, chat_id: int) -> None:
        chat = self.db.get_chat(chat_id)
        if not chat:
            return
        new = ctk.CTkInputDialog(text="New chat title:", title="Rename chat").get_input()
        if new and new.strip():
            self.db.rename_chat(chat_id, self._make_title(new))
            self.refresh_history()

    def show_history_menu(self, anchor, chat_id: int) -> None:
        def build(pop, close):
            add_menu_items(pop, [("Rename", "pen", lambda: self.rename_chat(chat_id)),
                                 ("Delete", "trash", lambda: self.delete_chat(chat_id), {"danger": True})], close, 170)
        Popover.show(anchor, build, width=190, align="right")

    def show_chat_menu(self, anchor) -> None:
        def build(pop, close):
            items = [("New chat", "plus", self.new_chat),
                     ("Export as TXT", "download", lambda: self.export_chat("TXT")),
                     ("Export as PDF", "download", lambda: self.export_chat("PDF")),
                     ("Copy conversation", "copy", self.copy_chat)]
            if self.current_chat_id is not None:
                cid = self.current_chat_id
                items += [("Rename chat", "pen", lambda: self.rename_chat(cid)),
                          ("Delete chat", "trash", lambda: self.delete_chat(cid), {"danger": True})]
            add_menu_items(pop, items, close, 200)
        Popover.show(anchor, build, width=220, align="right")

    def copy_chat(self) -> None:
        if self.current_chat_id is None:
            self.chat_page.show_status("Nothing to copy yet.", error=True)
            return
        lines = []
        for m in self.db.get_messages(self.current_chat_id):
            who = "You" if m["role"] == "user" else "Randan's GPT"
            lines.append(f"{who}: {clean_for_model(display_text(m['content']))}")
        self.clipboard_clear()
        self.clipboard_append("\n\n".join(lines))
        self.chat_page.show_status("Conversation copied to the clipboard.")

    @staticmethod
    def _make_title(text: str) -> str:
        title = " ".join(text.split())
        return title if len(title) <= 40 else title[:39] + "\u2026"

    # ============================================================ sending
    def send_or_stop(self) -> None:
        if self._generating:
            self.stop_generation()
        else:
            self.send_message()

    def send_message(self) -> None:
        if self._generating:
            return
        text = self.chat_page.get_text().strip()
        if not text and self._attachment:
            text = "Please summarize the attached file."
        if not text:                                       # empty prompt
            self.chat_page.show_status("Please type a message before sending.", error=True)
            return
        self.show_page("chat")
        stored = text
        if self._attachment:
            stored += f"\n\n[[ATTACHMENT:{self._attachment[0]}]]\n{self._attachment[1]}\n[[/ATTACHMENT]]"
            self.remove_attachment()
        self.chat_page.clear_input()
        self.chat_page.show_status("")

        if self.current_chat_id is None:
            self.current_chat_id = self.db.create_chat(self._make_title(text))
            self.refresh_history()
        self.chat_page.set_mode("chat")
        self.db.add_message(self.current_chat_id, "user", stored)
        self.chat_view.add_message("user", display_text(stored))
        self.chat_view.scroll_to_bottom(settle=True)

        # Memory commands are answered locally and instantly.
        if self.settings.get("memory_enabled"):
            reply = self.memory.handle(text)
            if reply is not None:
                self.db.add_message(self.current_chat_id, "assistant", reply, "memory")
                self.chat_view.add_message("assistant", reply, model="memory")
                self.chat_view.scroll_to_bottom(settle=True)
                self.refresh_history()
                return
        self._start_generation(self._resolve_model(text))

    def _system_prompt(self) -> str:
        prompt = SYSTEM_PROMPT
        tool = ALL_TOOLS.get(self.active_tool) if self.active_tool else None
        if tool:
            prompt += "\n\n" + tool.prompt
        if self.reasoning:
            prompt += "\n\n" + REASONING_PROMPT
        if self.research:
            prompt += "\n\n" + RESEARCH_PROMPT
        if self.settings.get("memory_enabled"):
            context = self.memory.context_block()
            if context:
                prompt += "\n\n" + context
        return prompt

    def _start_generation(self, model: str) -> None:
        limit = int(self.settings.get("history_messages"))
        history = self.db.get_recent_messages(self.current_chat_id, limit)
        messages = [{"role": "system", "content": self._system_prompt()}]
        messages += [{"role": m["role"], "content": model_text(clean_for_model(m["content"]))}
                     for m in history if m["role"] in ("user", "assistant")]
        num_ctx = int(self.settings.get("num_ctx"))
        tools = None
        if self.tools_on:
            question = display_text(history[-1]["content"]) if history else ""
            if self.mcp.has_connected():
                tools = self.mcp.tool_specs(question, k=8) or None
                if tools is None:
                    self.chat_page.show_status("No connected tool matches this question - answering without tools.")
            else:
                self.chat_page.show_status("Tools are on but no server is connected yet - see the Tools page.", error=True)
        options = {"num_ctx": max(num_ctx, 4096) if (self.research or tools) else num_ctx,
                   "temperature": float(self.settings.get("temperature"))}

        self._gen_id += 1
        self._stop_event = threading.Event()
        self._buffer = ""
        self._model_in_use = model
        self._generating = True
        self._bubble = self.chat_view.add_message("assistant", "", model=model, typing=True)
        self.chat_view.scroll_to_bottom(settle=True)
        self.chat_page.set_generating(True)
        self._sync_model_ui()

        threading.Thread(
            target=self._worker, args=(self._gen_id, model, messages, options, self._stop_event, tools),
            daemon=True).start()

    def _worker(self, gen_id: int, model: str, messages: list, options: dict,
                stop_event: threading.Event, tools: list | None = None) -> None:
        """Runs in a background thread - never touches widgets."""
        extra = {}
        if tools:
            extra = {"tools": tools,
                     "tool_runner": lambda name, args: self._run_tool(gen_id, stop_event, name, args)}
        try:
            for token in self.ollama.stream_chat(model, messages, stop_event, options, **extra):
                self._events.put((gen_id, "token", token))
            self._events.put((gen_id, "done", None))
        except OllamaError as exc:
            self._events.put((gen_id, "error", exc.user_message))
        except Exception as exc:  # noqa: BLE001
            logging.exception("Worker crashed")
            self._events.put((gen_id, "error", f"Unexpected error: {exc}"))

    def stop_generation(self) -> None:
        if not self._generating:
            return
        if self._stop_event:
            self._stop_event.set()
        self._finish_generation("done", None)      # keep what has streamed so far

    # ========================================================== event pump
    def _pump(self) -> None:
        try:
            if not self._dialog_open:
                self._drain_events()
        except Exception:  # noqa: BLE001 - keep the pump alive no matter what
            logging.exception("UI pump failed")
        finally:
            self.after(40, self._pump)

    def _drain_events(self) -> None:
        dirty, finish = False, None
        while True:
            try:
                gen_id, kind, payload = self._events.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self._apply_status(*payload)
                continue
            if kind == "mcp":                      # tool-server connection progress
                self.mcp_refresh_ui()
                self.tools_page.set_message(payload)
                if self.tools_on and not payload and self.mcp.has_connected():
                    self.chat_page.show_status("Tools ready - the model can use your tool servers.")
                continue
            if not self._generating or gen_id != self._gen_id:
                if kind == "approve":              # stale request: deny
                    payload[2].put(False)
                continue                           # stale event from a stopped run
            if kind == "approve":
                self._ask_approval(*payload)
                continue
            if kind == "token":
                self._buffer += payload
                dirty = True
            else:                                  # "done" or "error"
                finish = (kind, payload)
                break
        if dirty and self._bubble is not None:
            follow = self.chat_view.is_at_bottom()
            self._bubble.hide_typing()
            self._bubble.set_content(self._buffer, final=False)
            if follow:
                self.chat_view.scroll_to_bottom()
        if finish:
            self._finish_generation(*finish)

    def _finish_generation(self, kind: str, error_text: str | None) -> None:
        bubble, text, model = self._bubble, self._buffer, self._model_in_use
        self._generating = False
        self._stop_event = None
        self._bubble = None
        self.chat_page.set_generating(False)

        if bubble is not None:
            bubble.hide_typing()
            if text.strip():
                bubble.set_content(text, final=True)
                self.db.add_message(self.current_chat_id, "assistant", text, model)
            else:
                self.chat_view.remove_bubble(bubble)
        if kind == "error":
            self.chat_view.add_message("error", "\u26A0  " + (error_text or "Unknown error."))
        elif not text.strip():
            self.chat_page.show_status("The model returned an empty response. Try again.", error=True)

        self.chat_view.scroll_to_bottom(settle=True)
        self._sync_model_ui()
        self.refresh_history()
        self._check_ollama_async()
        self.chat_page.focus_input()

    # ============================================================ status
    def _check_ollama_async(self) -> None:
        def work() -> None:
            try:
                self._events.put((0, "status", (True, self.ollama.installed_models())))
            except Exception:  # noqa: BLE001
                self._events.put((0, "status", (False, [])))
        threading.Thread(target=work, daemon=True).start()

    def _apply_status(self, online: bool, installed: list) -> None:
        changed = online != self._online
        self._online, self._installed = online, installed
        if online:
            base = {m.tag for m in MODELS}
            extras = [t for t in installed if t not in base and not t.endswith(":latest")]
            if extras != self.settings.get("known_models"):
                self.settings.set("known_models", extras)
        self._refresh_models()
        self._sync_model_ui()
        if changed:
            if online:
                self.notify("Ollama is online", "Connected to your local Ollama server.")
            else:
                self.notify("Ollama is offline", "Start the Ollama app (or run `ollama serve`) to chat.")
        if online:
            missing = [m.tag for m in MODELS if m.tag not in installed and f"{m.tag}:latest" not in installed]
            key = ",".join(missing)
            if missing and key != getattr(self, "_missing_key", None):
                self.notify("Models not installed", "Run `ollama pull <name>` for: " + ", ".join(missing))
            self._missing_key = key
        if self.page == "dashboard":
            self.dashboard.refresh(self.db.stats(), bool(self._online), self._installed)

    # =========================================================== settings
    def on_setting_changed(self, key: str, value) -> None:
        if key == "theme":
            self.apply_theme(value)
            return
        if key != "default_model":
            self.settings.set(key, value)
        if key == "default_model":
            tag = self._label_to_tag.get(value, value)
            self.settings.set("default_model", tag)
            self.current_model, self.auto_mode = tag, False
            self._sync_model_ui()
            return
        elif key == "font_size":
            self.chat_page.set_font_size(int(value))
            self._reload_current_chat()

    def delete_memory(self, memory_id: int) -> None:
        self.db.delete_memory(memory_id)
        self.settings_page.refresh_memories(self.db.list_memories())

    def clear_memories(self) -> None:
        if messagebox.askyesno(APP_NAME, "Delete ALL saved memories?"):
            self.db.clear_memories()
            self.settings_page.refresh_memories([])

    # ============================================================= export
    def export_chat(self, kind: str) -> None:
        if self.current_chat_id is None:
            self.chat_page.show_status("Nothing to export yet - start a chat first.", error=True)
            return
        chat = self.db.get_chat(self.current_chat_id)
        messages = [dict(m, content=display_text(m["content"]) if m["role"] == "user" else m["content"])
                    for m in self.db.get_messages(self.current_chat_id)]
        pdf = kind == "PDF"
        safe = "".join(c for c in chat["title"] if c.isalnum() or c in " -_")[:40].strip() or "chat"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf" if pdf else ".txt", initialfile=safe,
            filetypes=[("PDF document", "*.pdf")] if pdf else [("Text file", "*.txt")])
        if not path:
            return
        try:
            (export_pdf if pdf else export_txt)(path, chat["title"], messages)
            self.chat_page.show_status(f"Exported to {path}")
        except Exception as exc:  # noqa: BLE001
            logging.exception("Export failed")
            self.chat_page.show_status(f"Export failed: {exc}", error=True)

    # =============================================================== exit
    def _on_close(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        try:
            self.mcp.close()                       # stop tool-server child processes
            self.db.close()
        finally:
            self.destroy()
