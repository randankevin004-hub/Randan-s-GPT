"""
backend/bridge.py
-----------------
The Python half of the HTML/CSS interface. pywebview exposes the public
methods of `Api` to JavaScript as `window.pywebview.api.<method>()` (each
returns a Promise). Anything the backend wants to push to the page (streamed
tokens, approvals, status) goes through `_emit` -> `App.event({...})` in JS.

No web server is involved: the page is a local file in a native window and
calls are made in-process. Internal state uses a leading underscore so that
pywebview does not expose it to JavaScript.
"""
from __future__ import annotations

import base64
import functools
import io
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from datetime import date, datetime, timedelta

from PIL import Image

from backend.auth import SupabaseAuth
from backend.catalog import USE_CASES, recommend
from backend.specs import detect_specs
from backend.prompts import (MAX_ATTACH_CHARS, REASONING_MODEL, REASONING_PROMPT, RESEARCH_PROMPT,
                             SYSTEM_PROMPT, display_text, model_text)
from backend.winfx import apply_window_style
from database.db import Database
from memory.memory_manager import MemoryManager
from models.mcp_client import McpManager, import_codex_servers, load_config, save_config
from models.ollama_client import OllamaError, OllamaService, clean_for_model
from models.router import DEFAULT_ROUTES, DEFAULT_MODEL, GENERAL_MODEL, MODELS, WRITING_MODEL, label_for, route
from settings.config import APP_NAME, APP_VERSION, Settings, app_data_dir, resource_path
from ui.export import export_pdf, export_txt
from ui.tools import ALL_TOOLS, MORE_TOOLS, TEMPLATES, TOOLS

PUBLIC_SETTINGS = ("theme", "font_size", "memory_enabled", "auto_mode", "default_model", "user_name",
                   "mcp_confirm", "show_history", "member_since", "reduce_effects", "onboarded", "auto_preview",
                   "perf_pref", "use_cases")


def needs_auth(fn):
    """Block data access until the user is signed in (when sign-in is required)."""
    @functools.wraps(fn)
    def wrapper(self, *a, **kw):
        if not self._ready():
            raise PermissionError("Sign in required")
        return fn(self, *a, **kw)
    return wrapper


class Api:
    def __init__(self, settings: Settings | None = None, db: Database | None = None) -> None:
        self._settings = settings or Settings()
        if not self._settings.get("member_since"):
            self._settings.set("member_since", datetime.now().strftime("%b %Y"))
        self._fixed_db = db                      # tests can inject a database
        self._db = db
        self._memory = MemoryManager(db) if db else None
        self._auth = SupabaseAuth()
        self._user: dict | None = None
        self._scope_ready, self._scope_uid, self._auth_checked = False, None, False
        self._refresh_thread = None
        self._specs: dict | None = None
        self._install: dict | None = None
        self._ollama = OllamaService()
        self._mcp = McpManager()
        self._mcp_cfg: dict = load_config()
        self._window = None
        self._sink = None                       # tests can capture events here
        self._online: bool | None = None
        self._installed: list = []
        self._gen: dict | None = None
        self._gen_counter = 0
        self._lock = threading.RLock()
        self._approvals: dict = {}

    # ----------------------------------------------------------- plumbing
    def _attach_window(self, window) -> None:
        self._window = window

    def _emit(self, event: dict) -> None:
        """Push an event to the page (safe to call from any thread)."""
        if self._sink:
            self._sink(event)
        if self._window is not None:
            try:
                self._window.evaluate_js(f"window.App && App.event({json.dumps(event)})")
            except Exception:  # noqa: BLE001 - window may be closing
                logging.debug("emit failed", exc_info=True)

    def _shutdown(self) -> None:
        if self._gen and self._gen.get("stop"):
            self._gen["stop"].set()
        try:
            self._mcp.close()
            if self._db is not None:
                self._db.close()
        except Exception:  # noqa: BLE001
            logging.exception("shutdown")

    @staticmethod
    def _msg(row: dict) -> dict:
        text = display_text(row["content"]) if row["role"] == "user" else row["content"]
        return {"id": row["id"], "role": row["role"], "content": text, "model": row.get("model"),
                "label": label_for(row["model"]) if row.get("model") and row["model"] != "memory" else row.get("model"),
                "time": row["created_at"]}

    def _chats(self) -> list:
        if self._db is None:
            return []
        return [{"id": c["id"], "title": c["title"], "updated": c["updated_at"]} for c in self._db.list_chats()]

    def _public_settings(self) -> dict:
        out = {k: self._settings.get(k) for k in PUBLIC_SETTINGS}
        out["user_name"] = self._user_name()
        return out

    def _tool(self, t) -> dict:
        model = self._ensure_installed(self._route_map().get(t.category) or t.model)
        return {"key": t.key, "label": t.label, "icon": t.icon, "model": model, "modelLabel": label_for(model)}

    def _route_map(self) -> dict:
        """The user's category -> model choices (from setup), limited to models that are installed."""
        mapping = dict(self._settings.get("route_map") or {})
        if self._online and self._installed:
            have = set(self._installed) | {t.removesuffix(":latest") for t in self._installed}
            mapping = {k: v for k, v in mapping.items() if v in have}
        return mapping

    def _ensure_installed(self, tag: str) -> str:
        """Fall back to something that exists if `tag` isn't installed."""
        if not (self._online and self._installed):
            return tag
        have = set(self._installed) | {t.removesuffix(":latest") for t in self._installed}
        if tag in have:
            return tag
        default = self._settings.get("default_model")
        return default if default in have else sorted(have)[0]

    def _model_list(self) -> list:
        base = [m.tag for m in MODELS]
        if self._online and self._installed:
            tags = [t for t in base if t in self._installed or f"{t}:latest" in self._installed]
            tags += [t for t in self._installed if t not in tags and not t.endswith(":latest")]
            tags = tags or base
        else:
            tags = base + [t for t in self._settings.get("known_models") if t not in base]
        current = self._settings.get("default_model")
        if current and current not in tags:
            tags.append(current)
        return [{"tag": t, "label": label_for(t)} for t in tags]

    # --------------------------------------------- accounts & per-user data
    def _ready(self) -> bool:
        return (not self._auth.required) or self._auth.session is not None

    def _activate(self, user: dict | None) -> None:
        """Switch to a user's private database (or the local one when signed out / auth not configured)."""
        uid = user["id"] if user else None
        if self._scope_ready and uid == self._scope_uid and self._db is not None:
            return
        old = self._db
        if self._fixed_db is not None:
            db = self._fixed_db
        elif user:
            folder = app_data_dir() / "users" / uid
            folder.mkdir(parents=True, exist_ok=True)
            db = Database(folder / "randans_gpt.db")
        else:
            db = Database()
        self._db, self._memory, self._user = db, MemoryManager(db), user
        self._scope_ready, self._scope_uid = True, uid
        if old is not None and old is not db and old is not self._fixed_db:
            old.close()

    def _user_dir(self):
        return app_data_dir() / "users" / self._user["id"] if self._user else app_data_dir()

    def _profile(self) -> dict:
        try:
            return json.loads((self._user_dir() / "profile.json").read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    def _profile_save(self, **kv) -> None:
        data = {**self._profile(), **kv}
        (self._user_dir() / "profile.json").write_text(json.dumps(data), "utf-8")

    def _user_name(self) -> str:
        if self._user:
            return self._profile().get("user_name") or self._user.get("name") or "Friend"
        return self._settings.get("user_name")

    def _avatar_path(self) -> str:
        return self._profile().get("avatar_path", "") if self._user else self._settings.get("avatar_path")

    def _set_avatar_path(self, path: str) -> None:
        if self._user:
            self._profile_save(avatar_path=path)
        else:
            self._settings.set("avatar_path", path)

    def _ensure_refresh_loop(self) -> None:
        """Keep the access token fresh; tell the page if the session is revoked."""
        if self._refresh_thread and self._refresh_thread.is_alive():
            return

        def loop() -> None:
            while self._auth.session:
                time.sleep(240)
                if self._auth.session and not self._auth.ensure_fresh():
                    self._emit({"type": "auth_lost"})
                    break
        self._refresh_thread = threading.Thread(target=loop, daemon=True)
        self._refresh_thread.start()

    def _after_auth(self, result: dict) -> dict:
        if result.get("ok") and self._auth.session:
            self._activate(self._auth.user)
            self._ensure_refresh_loop()
        return result

    def auth_state(self) -> dict:
        return self._auth.public_state()

    def auth_sign_up(self, email: str, password: str, name: str = "") -> dict:
        return self._after_auth(self._auth.sign_up(email, password, name))

    def auth_sign_in(self, email: str, password: str) -> dict:
        return self._after_auth(self._auth.sign_in(email, password))

    def auth_send_code(self, email: str) -> dict:
        return self._auth.send_code(email)

    def auth_verify(self, email: str, code: str, kind: str = "email") -> dict:
        return self._after_auth(self._auth.verify_code(email, code, kind))

    def auth_resend(self, email: str) -> dict:
        return self._auth.resend(email)

    def auth_reset(self, email: str) -> dict:
        return self._auth.reset_password(email)

    def auth_set_password(self, password: str) -> dict:
        return self._auth.set_password(password)

    def auth_guest(self) -> dict:
        """Use the app without an account (only when sign-in isn't required)."""
        if self._auth.required:
            return {"ok": False, "error": "An account is required."}
        self._activate(None)
        return {"ok": True}

    def auth_sign_out(self) -> dict:
        if self._gen and not self._gen["done"]:
            self.stop()
        self._auth.sign_out()
        if self._auth.required:
            old, self._db, self._memory, self._user = self._db, None, None, None
            self._scope_ready = False
            if old is not None and old is not self._fixed_db:
                old.close()
        else:
            self._activate(None)
        return {"ok": True}

    # ------------------------------------------------------------- startup
    def boot(self) -> dict:
        """Everything the page needs on first load (and again after signing in)."""
        if not self._auth_checked:
            self._auth_checked = True
            if self._auth.configured and self._auth.restore().get("ok"):
                self._after_auth({"ok": True})
        ready = self._ready()
        if ready and not self._scope_ready:
            self._activate(self._auth.user if self._auth.session else None)
        return {
            "app": APP_NAME, "version": APP_VERSION, "platform": sys.platform, "dataDir": str(app_data_dir()),
            "auth": self._auth.public_state(), "ready": ready,
            "settings": self._public_settings(), "avatar": self._avatar_data() if ready else "",
            "models": self._model_list(),
            "tools": [self._tool(t) for t in TOOLS], "moreTools": [self._tool(t) for t in MORE_TOOLS],
            "templates": [{"label": a, "text": b} for a, b in TEMPLATES],
            "chats": self._chats() if ready else [], "reasoningModel": REASONING_MODEL,
            "useCases": USE_CASES,
            "legal": {"terms": self._auth.config.get("terms_url", ""), "privacy": self._auth.config.get("privacy_url", "")},
        }

    def check_updates(self) -> dict:
        """Check the configured public GitHub Releases feed without sending user data."""
        repo = str(self._auth.config.get("updates_repo", "")).strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            return {"ok": False, "error": "Update repository is not configured."}

        request = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases/latest",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "RandansGPT"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                release = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            logging.info("Update check failed: %s", exc)
            return {"ok": False, "error": "Could not check for updates. Check your internet connection and try again."}

        if not isinstance(release, dict):
            return {"ok": False, "error": "GitHub returned invalid release data."}
        tag = str(release.get("tag_name", "")).strip()
        latest_version = tag.removeprefix("v")
        version_pattern = r"\d+(?:\.\d+){1,3}"
        if not re.fullmatch(version_pattern, latest_version):
            return {"ok": False, "error": "The latest release has an invalid version tag."}
        release_url = release.get("html_url", "")
        if not isinstance(release_url, str) or not release_url.startswith(
            f"https://github.com/{repo}/releases/tag/"
        ):
            return {"ok": False, "error": "GitHub returned an invalid release link."}

        def version_parts(version: str) -> tuple[int, ...]:
            return tuple(int(part) for part in version.split("."))

        current = APP_VERSION.removeprefix("v")
        if not re.fullmatch(version_pattern, current):
            return {"ok": False, "error": "This app version cannot be compared with the release."}
        current_parts, latest_parts = version_parts(current), version_parts(latest_version)
        width = max(len(current_parts), len(latest_parts))
        available = current_parts + (0,) * (width - len(current_parts)) < latest_parts + (0,) * (width - len(latest_parts))
        return {
            "ok": True,
            "available": available,
            "current": APP_VERSION,
            "latest": latest_version,
            "url": release_url,
        }

    def check_ollama(self) -> dict:
        try:
            installed, online = self._ollama.installed_models(), True
        except Exception:  # noqa: BLE001
            installed, online = [], False
        self._online, self._installed = online, installed
        base = {m.tag for m in MODELS}
        if online:
            extras = [t for t in installed if t not in base and not t.endswith(":latest")]
            if extras != self._settings.get("known_models"):
                self._settings.set("known_models", extras)
        missing = [m.tag for m in MODELS if online and m.tag not in installed and f"{m.tag}:latest" not in installed]
        return {"online": online, "installed": installed, "models": self._model_list(), "missing": missing}

    # ------------------------------------------------------------ settings
    def set_setting(self, key: str, value) -> dict:
        if key not in PUBLIC_SETTINGS or key in ("member_since", "user_name"):
            return {"ok": False}
        if key == "font_size":
            value = int(value)
        elif key in ("memory_enabled", "auto_mode", "mcp_confirm", "show_history", "reduce_effects", "onboarded", "auto_preview"):
            value = bool(value)
        elif key == "use_cases":
            value = [str(v) for v in value]
        self._settings.set(key, value)
        if key == "theme" and self._window is not None:
            apply_window_style(self._window, value == "Dark", resource_path("assets/icon.ico"))
        return {"ok": True, "settings": self._public_settings()}

    def set_user_name(self, name: str) -> str:
        name = " ".join(str(name).split())[:30] or "Friend"
        if self._user:
            self._profile_save(user_name=name)
            threading.Thread(target=self._auth.update_name, args=(name,), daemon=True).start()
        else:
            self._settings.set("user_name", name)
        return name

    # ---------------------------------------------------------------- chats
    @needs_auth
    def list_chats(self) -> list:
        return self._chats()

    @needs_auth
    def open_chat(self, chat_id: int) -> dict:
        chat = self._db.get_chat(int(chat_id))
        if not chat:
            return {"error": "Chat not found"}
        return {"id": chat["id"], "title": chat["title"],
                "messages": [self._msg(m) for m in self._db.get_messages(chat["id"])]}

    @needs_auth
    def delete_chat(self, chat_id: int) -> list:
        self._db.delete_chat(int(chat_id))
        return self._chats()

    @needs_auth
    def rename_chat(self, chat_id: int, title: str) -> list:
        title = " ".join(str(title).split())[:60]
        if title:
            self._db.rename_chat(int(chat_id), title)
        return self._chats()

    @staticmethod
    def _make_title(text: str) -> str:
        title = " ".join(text.split())
        return title if len(title) <= 40 else title[:39] + "\u2026"

    # -------------------------------------------------------------- sending
    @needs_auth
    def send(self, payload: dict) -> dict:
        """Store the user's message and start generating (or answer a memory command)."""
        text = str(payload.get("text", "")).strip()
        attach = payload.get("attachment")
        if not text and attach:
            text = "Please summarize the attached file."
        if not text:
            return {"error": "Please type a message before sending."}
        with self._lock:
            if self._gen and not self._gen["done"]:
                return {"error": "Please wait for the current reply to finish, or press Stop."}
        stored = text
        if attach:
            stored += f"\n\n[[ATTACHMENT:{attach['name']}]]\n{attach['text']}\n[[/ATTACHMENT]]"
        chat_id, new_chat = payload.get("chat_id"), False
        if not chat_id:
            chat_id, new_chat = self._db.create_chat(self._make_title(text)), True
        user_id = self._db.add_message(chat_id, "user", stored)
        result = {"chat_id": chat_id, "new_chat": new_chat, "model": None, "gen": None, "assistant": None,
                  "user": self._msg({"id": user_id, "role": "user", "content": stored, "model": None,
                                     "created_at": datetime.now().isoformat(sep=" ", timespec="seconds")})}
        if self._settings.get("memory_enabled"):
            reply = self._memory.handle(text)
            if reply is not None:
                mid = self._db.add_message(chat_id, "assistant", reply, "memory")
                result["assistant"] = self._msg(self._db.get_messages(chat_id)[-1] | {"id": mid})
                result["chats"] = self._chats()
                return result
        opts = payload.get("options", {})
        model = self._resolve_model(text, opts)
        result["model"], result["modelLabel"] = model, label_for(model)
        result["gen"] = self._start_generation(chat_id, model, opts, text)
        result["chats"] = self._chats()
        return result

    def _resolve_model(self, text: str, opts: dict) -> str:
        if opts.get("reasoning"):
            return REASONING_MODEL
        chosen = opts.get("model") or "auto"
        if chosen == "auto":
            mapping = self._route_map()
            model = route(text, mapping)
            if opts.get("research") and model == (mapping.get("general") or GENERAL_MODEL):
                model = mapping.get("writing") or WRITING_MODEL
            return self._ensure_installed(model)
        return chosen

    def _system_prompt(self, opts: dict) -> str:
        prompt = SYSTEM_PROMPT
        tool = ALL_TOOLS.get(opts.get("tool")) if opts.get("tool") else None
        if tool:
            prompt += "\n\n" + tool.prompt
        if opts.get("reasoning"):
            prompt += "\n\n" + REASONING_PROMPT
        if opts.get("research"):
            prompt += "\n\n" + RESEARCH_PROMPT
        if self._settings.get("memory_enabled"):
            context = self._memory.context_block()
            if context:
                prompt += "\n\n" + context
        return prompt

    def _start_generation(self, chat_id: int, model: str, opts: dict, question: str) -> int:
        history = self._db.get_recent_messages(chat_id, int(self._settings.get("history_messages")))
        messages = [{"role": "system", "content": self._system_prompt(opts)}]
        messages += [{"role": m["role"], "content": model_text(clean_for_model(m["content"]))}
                     for m in history if m["role"] in ("user", "assistant")]
        tools, note = None, None
        if opts.get("tools"):
            if self._mcp.has_connected():
                tools = self._mcp.tool_specs(question, k=8) or None
                if tools is None:
                    note = "No connected tool matches this question - answering without tools."
            else:
                note = "Tools are on but no server is connected yet - open Tools to connect one."
        num_ctx = int(self._settings.get("num_ctx"))
        options = {"num_ctx": max(num_ctx, 4096) if (opts.get("research") or tools) else num_ctx,
                   "temperature": float(self._settings.get("temperature"))}
        with self._lock:
            self._gen_counter += 1
            gen = {"id": self._gen_counter, "chat_id": chat_id, "model": model, "buffer": "",
                   "stop": threading.Event(), "done": False}
            self._gen = gen
        threading.Thread(target=self._worker, args=(gen, messages, options, tools), daemon=True).start()
        if note:
            self._emit({"type": "info", "text": note})
        return gen["id"]

    def _worker(self, gen: dict, messages: list, options: dict, tools: list | None) -> None:
        """Background thread: stream tokens to the page in ~40 ms batches."""
        extra = {}
        if tools:
            extra = {"tools": tools, "tool_runner": lambda name, args: self._run_tool(gen, name, args)}
        pending, last = "", time.monotonic()
        try:
            for token in self._ollama.stream_chat(gen["model"], messages, gen["stop"], options, **extra):
                if gen["done"]:
                    return
                gen["buffer"] += token
                pending += token
                if time.monotonic() - last >= 0.04:
                    self._emit({"type": "token", "gen": gen["id"], "text": pending})
                    pending, last = "", time.monotonic()
            if pending and not gen["done"]:
                self._emit({"type": "token", "gen": gen["id"], "text": pending})
            self._finish(gen, None)
        except OllamaError as exc:
            if pending and not gen["done"]:
                self._emit({"type": "token", "gen": gen["id"], "text": pending})
            self._finish(gen, exc.user_message)
        except Exception as exc:  # noqa: BLE001
            logging.exception("Worker crashed")
            self._finish(gen, f"Unexpected error: {exc}")

    def _finish(self, gen: dict, error: str | None) -> None:
        with self._lock:
            if gen["done"]:
                return
            gen["done"] = True
        text, saved = gen["buffer"], None
        if text.strip():
            mid = self._db.add_message(gen["chat_id"], "assistant", text, gen["model"])
            saved = self._msg(self._db.get_messages(gen["chat_id"])[-1] | {"id": mid})
        self._emit({"type": "done", "gen": gen["id"], "message": saved, "error": error,
                    "chats": self._chats()})

    def stop(self) -> bool:
        gen = self._gen
        if gen and not gen["done"]:
            gen["stop"].set()
            self._finish(gen, None)       # keep what has streamed so far
            return True
        return False

    # ---------------------------------------------------------- tool calls
    def _run_tool(self, gen: dict, alias: str, args: dict) -> str:
        """Worker thread: ask the page for permission, then run the MCP tool."""
        if self._settings.get("mcp_confirm"):
            rid = uuid.uuid4().hex
            ev = threading.Event()
            self._approvals[rid] = {"event": ev, "allow": False}
            self._emit({"type": "approve", "id": rid, "tool": self._mcp.describe(alias),
                        "args": json.dumps(args, indent=2, ensure_ascii=False)[:800]})
            while not ev.wait(0.2):
                if gen["stop"].is_set() or gen["done"]:
                    self._approvals.pop(rid, None)
                    return "The user did not allow this tool to run."
            if not self._approvals.pop(rid)["allow"]:
                return "The user did not allow this tool to run."
        try:
            out = self._mcp.call_alias(alias, args)
        except Exception as exc:  # noqa: BLE001
            return f"Error: {exc}"
        return out if len(out) <= 6000 else out[:6000] + "\n...[output truncated]"

    def approve(self, request_id: str, allow: bool) -> bool:
        item = self._approvals.get(request_id)
        if item:
            item["allow"] = bool(allow)
            item["event"].set()
        return bool(item)

    # ------------------------------------------------------- MCP management
    def mcp_state(self) -> list:
        return self._mcp.snapshot(self._mcp_cfg)

    def mcp_import(self) -> dict:
        try:
            found = import_codex_servers()
        except FileNotFoundError as exc:
            return {"ok": False, "message": f"Codex config not found: {exc}", "servers": self.mcp_state()}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": f"Couldn't read Codex config: {exc}", "servers": self.mcp_state()}
        new = [n for n in found if n not in self._mcp_cfg]
        for name in new:
            self._mcp_cfg[name] = found[name]
        save_config(self._mcp_cfg)
        if new:
            self.mcp_connect()
        return {"ok": True, "servers": self.mcp_state(),
                "message": f"Imported {len(new)} new server(s): {', '.join(new) or 'none - already added'}"}

    def mcp_add(self, name: str, command: str, args: str) -> list:
        import shlex
        name, command = name.strip(), command.strip()
        if name and command:
            self._mcp_cfg[name] = {"command": command, "enabled": True,
                                   "args": shlex.split(args, posix=sys.platform != "win32")}
            save_config(self._mcp_cfg)
            self.mcp_connect()
        return self.mcp_state()

    def mcp_remove(self, name: str) -> list:
        self._mcp_cfg.pop(name, None)
        save_config(self._mcp_cfg)
        threading.Thread(target=self._mcp.disconnect, args=(name,), daemon=True).start()
        return self.mcp_state()

    def mcp_enable(self, name: str, on: bool) -> list:
        if name in self._mcp_cfg:
            self._mcp_cfg[name]["enabled"] = bool(on)
            save_config(self._mcp_cfg)
            if on:
                self.mcp_connect()
            else:
                threading.Thread(target=self._mcp.disconnect, args=(name,), daemon=True).start()
        return self.mcp_state()

    def mcp_connect(self) -> bool:
        """Connect every enabled server in the background; the page gets 'mcp' events."""
        todo = {n: c for n, c in self._mcp_cfg.items() if c.get("enabled", True)}

        def work() -> None:
            for name, cfg in todo.items():
                self._emit({"type": "mcp", "busy": True, "message": f"Connecting {name}..."})
                try:
                    self._mcp.connect(name, cfg)
                except Exception as exc:  # noqa: BLE001
                    logging.warning("MCP connect failed for %s: %s", name, exc)
                self._emit({"type": "mcp", "busy": True, "message": ""})
            self._emit({"type": "mcp", "busy": False, "message": ""})
        if todo:
            threading.Thread(target=work, daemon=True).start()
        return bool(todo)

    def mcp_ready(self) -> bool:
        return self._mcp.has_connected()

    # ---------------------------------------------------------- files, etc.
    def _dialog(self, kind: str, **kwargs):
        import webview
        dialog = getattr(webview, "FileDialog", None)
        mode = getattr(dialog, kind) if dialog else getattr(webview, f"{kind}_DIALOG")
        return self._window.create_file_dialog(mode, **kwargs)

    def pick_attachment(self) -> dict:
        if self._window is None:
            return {"error": "No window"}
        picked = self._dialog("OPEN", file_types=("Text and code (*.txt;*.md;*.py;*.js;*.ts;*.html;*.css;*.json;*.csv;"
                                                  "*.xml;*.log;*.java;*.c;*.cpp;*.cs;*.kt;*.sql;*.yml;*.yaml;*.ini)",
                                                  "All files (*.*)"))
        if not picked:
            return {"cancelled": True}
        path = picked[0] if isinstance(picked, (list, tuple)) else picked
        return self._read_attachment(path)

    @staticmethod
    def _read_attachment(path: str) -> dict:
        try:
            with open(path, "rb") as fh:
                raw = fh.read(2_000_000)
            if b"\x00" in raw[:4096]:
                return {"error": "That doesn't look like a text file."}
            text = raw.decode("utf-8", errors="replace")
        except OSError as exc:
            return {"error": f"Couldn't read the file: {exc}"}
        note = ""
        if len(text) > MAX_ATTACH_CHARS:
            text, note = text[:MAX_ATTACH_CHARS], f"Truncated to {MAX_ATTACH_CHARS:,} characters."
        return {"name": os.path.basename(path), "text": text, "note": note}

    def _avatar_data(self) -> str:
        path = self._avatar_path()
        if path and os.path.exists(path):
            with open(path, "rb") as fh:
                return "data:image/png;base64," + base64.b64encode(fh.read()).decode()
        return ""

    def pick_avatar(self) -> dict:
        if self._window is None:
            return {"error": "No window"}
        picked = self._dialog("OPEN", file_types=("Images (*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif)", "All files (*.*)"))
        if not picked:
            return {"cancelled": True}
        return self._save_avatar(picked[0] if isinstance(picked, (list, tuple)) else picked)

    def _save_avatar(self, path: str) -> dict:
        try:
            img = Image.open(path).convert("RGB")
            side = min(img.size)
            left, top = (img.width - side) // 2, (img.height - side) // 2
            img = img.crop((left, top, left + side, top + side)).resize((256, 256), Image.LANCZOS)
            dest = self._user_dir() / "avatar.png"
            img.save(dest)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Couldn't use that image: {exc}"}
        self._set_avatar_path(str(dest))
        return {"avatar": self._avatar_data()}

    def remove_avatar(self) -> dict:
        self._set_avatar_path("")
        return {"avatar": ""}

    @needs_auth
    def export_chat(self, chat_id: int, kind: str) -> dict:
        chat = self._db.get_chat(int(chat_id))
        if not chat or self._window is None:
            return {"error": "Nothing to export yet."}
        pdf = kind.upper() == "PDF"
        safe = "".join(c for c in chat["title"] if c.isalnum() or c in " -_")[:40].strip() or "chat"
        path = self._dialog("SAVE", save_filename=f"{safe}.{'pdf' if pdf else 'txt'}")
        if not path:
            return {"cancelled": True}
        path = path[0] if isinstance(path, (list, tuple)) else path
        messages = [dict(m, content=display_text(m["content"]) if m["role"] == "user" else m["content"])
                    for m in self._db.get_messages(chat["id"])]
        try:
            (export_pdf if pdf else export_txt)(path, chat["title"], messages)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Export failed: {exc}"}
        return {"ok": True, "path": path}

    # ------------------------------------------------------ memory, stats
    @needs_auth
    def memories(self) -> list:
        return self._db.list_memories()

    @needs_auth
    def delete_memory(self, memory_id: int) -> list:
        self._db.delete_memory(int(memory_id))
        return self._db.list_memories()

    @needs_auth
    def clear_memories(self) -> list:
        self._db.clear_memories()
        return []

    @needs_auth
    def stats(self) -> dict:
        s = self._db.stats()
        days = [date.today() - timedelta(days=i) for i in range(6, -1, -1)]
        return {"chats": s["chats"], "questions": s["questions"], "messages": s["messages"],
                "memories": s["memories"],
                "daily": [{"label": d.strftime("%a"), "count": s["daily"].get(d.isoformat(), 0)} for d in days],
                "models": [{"label": label_for(r["model"]), "count": r["c"]} for r in s["by_model"][:6]]}

    # ---------------------------------------- setup wizard (specs -> models)
    def get_specs(self) -> dict:
        """Detect this PC's hardware (cached; pass through rescan_specs to refresh)."""
        if self._specs is None:
            self._specs = detect_specs()
        return self._specs

    def rescan_specs(self) -> dict:
        self._specs = None
        return self.get_specs()

    def recommend_models(self, uses: list, pref: str = "balanced") -> dict:
        status = self.check_ollama()
        plan = recommend(self.get_specs(), list(uses), pref if pref in ("speed", "balanced", "quality") else "balanced",
                         status["installed"])
        plan["ollama_online"] = status["online"]
        return plan

    def start_install(self, tags: list) -> dict:
        """Download models one by one; progress arrives as 'pull' events."""
        with self._lock:
            if self._install and self._install.get("running"):
                return {"ok": False, "error": "A download is already running."}
        try:
            self._ollama.installed_models()
        except OllamaError as exc:
            return {"ok": False, "code": "ollama_down", "error": exc.user_message}
        stop = threading.Event()
        self._install = {"running": True, "stop": stop}
        threading.Thread(target=self._install_worker, args=(list(tags), stop), daemon=True).start()
        return {"ok": True}

    def _install_worker(self, tags: list, stop: threading.Event) -> None:
        ok, failed = [], []
        for tag in tags:
            if stop.is_set():
                break
            layers: dict = {}
            state = {"t0": time.monotonic(), "last": 0.0, "bytes": 0, "tlast": time.monotonic()}

            def progress(status, completed, total, digest, tag=tag, layers=layers, state=state) -> None:
                if digest and total:
                    layers[digest] = (completed or 0, total)
                done, whole = sum(c for c, _ in layers.values()), sum(t for _, t in layers.values())
                now = time.monotonic()
                if now - state["last"] < 0.25 and not (whole and done >= whole):
                    return
                speed = max(0.0, (done - state["bytes"]) / max(now - state["tlast"], 1e-3)) if state["bytes"] else 0.0
                state.update(last=now, bytes=done, tlast=now)
                eta = int((whole - done) / speed) if speed > 1 else None
                self._emit({"type": "pull", "tag": tag, "status": status, "pct": round(100 * done / whole, 1) if whole else 0,
                            "mb": round(done / 1e6), "total_mb": round(whole / 1e6), "speed_mbs": round(speed / 1e6, 1), "eta": eta})
            self._emit({"type": "pull", "tag": tag, "status": "starting", "pct": 0})
            try:
                if self._ollama.pull(tag, progress, stop):
                    ok.append(tag)
                    self._emit({"type": "pull", "tag": tag, "status": "done", "pct": 100, "done": True})
            except OllamaError as exc:
                failed.append({"tag": tag, "error": exc.user_message})
                self._emit({"type": "pull", "tag": tag, "error": exc.user_message})
            except Exception as exc:  # noqa: BLE001
                logging.exception("pull failed")
                failed.append({"tag": tag, "error": str(exc)})
                self._emit({"type": "pull", "tag": tag, "error": str(exc)})
        self._install = None
        self._emit({"type": "pull_done", "ok": ok, "failed": failed, "cancelled": stop.is_set()})

    def cancel_install(self) -> bool:
        if self._install:
            self._install["stop"].set()
            return True
        return False

    def finish_setup(self, config: dict) -> dict:
        """Save the wizard's choices: routing map, default model, use cases."""
        route_map = {k: v for k, v in (config.get("route_map") or {}).items() if isinstance(v, str) and v}
        self._settings.set("route_map", route_map)
        default = config.get("default_model") or route_map.get("general")
        if default:
            self._settings.set("default_model", default)
        self._settings.set("use_cases", [str(u) for u in config.get("uses", [])])
        self._settings.set("perf_pref", config.get("pref", "balanced"))
        self._settings.set("auto_mode", bool(route_map))          # smart routing now uses the user's own models
        self._settings.set("onboarded", True)
        self.check_ollama()
        return {"settings": self._public_settings(), "models": self._model_list(),
                "tools": [self._tool(t) for t in TOOLS], "moreTools": [self._tool(t) for t in MORE_TOOLS]}

    # -------------------------------------------------------- code preview
    def save_text(self, filename: str, text: str) -> dict:
        if self._window is None:
            return {"error": "No window"}
        path = self._dialog("SAVE", save_filename=os.path.basename(filename) or "page.html")
        if not path:
            return {"cancelled": True}
        path = path[0] if isinstance(path, (list, tuple)) else path
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            return {"error": f"Couldn't save: {exc}"}
        return {"ok": True, "path": path}

    def open_preview_external(self, html: str) -> dict:
        """Open the generated page in the default browser (handy for testing on a real browser)."""
        folder = app_data_dir() / "previews"
        folder.mkdir(exist_ok=True)
        target = folder / "preview.html"
        target.write_text(html, "utf-8")
        webbrowser.open(target.as_uri())
        return {"ok": True}

    # ----------------------------------------------------------- utilities
    def start_voice(self) -> dict:
        """Open Windows voice typing (Win+H)."""
        if sys.platform != "win32":
            return {"ok": False, "message": "Voice typing uses Windows' built-in dictation (Win+H) - Windows only."}
        import ctypes
        k = ctypes.windll.user32.keybd_event
        k(0x5B, 0, 0, 0); k(0x48, 0, 0, 0); k(0x48, 0, 2, 0); k(0x5B, 0, 2, 0)  # noqa: E702
        return {"ok": True, "message": "Listening... speak now. Press Win+H again to stop."}

    def open_url(self, url: str) -> bool:
        if str(url).startswith(("http://", "https://")):
            webbrowser.open(url)
            return True
        return False

    def open_data_folder(self) -> bool:
        path = str(app_data_dir())
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        else:
            webbrowser.open("file://" + path)
        return True

    def quit(self) -> None:
        if self._window is not None:
            self._window.destroy()
