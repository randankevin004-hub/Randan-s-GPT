"""
models/mcp_client.py
--------------------
MCP (Model Context Protocol) client: lets Randan's GPT use the same tool
servers you set up for Codex (e.g. REA).

* Server definitions live in %APPDATA%\\RandansGPT\\mcp_servers.json and can be
  imported from Codex's  ~/.codex/config.toml  ([mcp_servers.<name>] tables).
* Each server runs as a child process (stdio) or a remote URL (streamable HTTP)
  on a private asyncio loop in a background thread; the public API is
  synchronous and thread-safe.
* Local models have small context windows, so instead of sending hundreds of
  tool schemas, tool_specs() picks the few tools most relevant to the question.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from settings.config import app_data_dir

try:                                    # Python 3.11+
    import tomllib
except ModuleNotFoundError:             # pragma: no cover
    try:
        import tomli as tomllib         # type: ignore
    except ModuleNotFoundError:
        tomllib = None                  # type: ignore

CONNECT_TIMEOUT = 90     # seconds (some servers load big databases on start)
CALL_TIMEOUT = 180


# ------------------------------------------------------------------ config
def config_path() -> Path:
    return app_data_dir() / "mcp_servers.json"


def load_config() -> dict:
    try:
        data = json.loads(config_path().read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(servers: dict) -> None:
    config_path().write_text(json.dumps(servers, indent=2), "utf-8")


def codex_config_path() -> Path:
    home = os.environ.get("CODEX_HOME")
    return (Path(home) if home else Path.home() / ".codex") / "config.toml"


def import_codex_servers() -> dict:
    """Read [mcp_servers.*] from Codex's config.toml. Raises FileNotFoundError."""
    path = codex_config_path()
    if not path.exists():
        raise FileNotFoundError(str(path))
    if tomllib is None:
        raise RuntimeError("Reading config.toml needs Python 3.11+ or:  pip install tomli")
    data = tomllib.loads(path.read_text("utf-8"))
    servers: dict = {}
    for name, cfg in (data.get("mcp_servers") or {}).items():
        entry: dict = {"enabled": bool(cfg.get("enabled", True))}
        if cfg.get("url"):
            entry["url"] = cfg["url"]
        else:
            entry["command"] = cfg.get("command", "")
            entry["args"] = [str(a) for a in cfg.get("args", [])]
        if cfg.get("env"):
            entry["env"] = {k: str(v) for k, v in cfg["env"].items()}
        if cfg.get("cwd"):
            entry["cwd"] = str(cfg["cwd"])
        servers[name] = entry
    return servers


# ------------------------------------------------------------------ helpers
def _short_error(exc: BaseException) -> str:
    subs = getattr(exc, "exceptions", None)          # ExceptionGroup from anyio
    if subs:
        return _short_error(subs[0])
    return (str(exc) or type(exc).__name__)[:300]


def _slim(schema: Any) -> Any:
    """Shrink a JSON schema (long descriptions cost context tokens)."""
    if isinstance(schema, dict):
        out = {}
        for key, val in schema.items():
            if key in ("title", "examples", "$schema"):
                continue
            out[key] = val[:120] if key == "description" and isinstance(val, str) else _slim(val)
        return out
    if isinstance(schema, list):
        return [_slim(v) for v in schema]
    return schema


_STOP = {"the", "and", "for", "with", "this", "that", "from", "into", "what", "how", "can", "you",
         "please", "show", "use", "using", "are", "was", "have", "has", "about", "tell", "give"}


def _tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3 and t not in _STOP]


def _score(query_tokens: list, name: str, description: str) -> int:
    name_t, desc_t = _tokens(name), _tokens(description)
    score = 0
    for q in query_tokens:
        stem = q[:5]
        if any(t.startswith(stem) for t in name_t):
            score += 3
        elif any(t.startswith(stem) for t in desc_t):
            score += 1
    return score


@dataclass
class ServerState:
    name: str
    cfg: dict
    status: str = "idle"          # idle | connecting | connected | error | stopped
    error: str = ""
    tools: list = field(default_factory=list)
    session: Any = None
    stop: Any = None
    task: Any = None


class McpManager:
    def __init__(self) -> None:
        self.servers: dict[str, ServerState] = {}
        self._alias: dict[str, tuple] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------ plumbing
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                threading.Thread(target=self._loop.run_forever, daemon=True, name="mcp-loop").start()
            return self._loop

    def _run(self, coro, timeout: float):
        return asyncio.run_coroutine_threadsafe(coro, self._ensure_loop()).result(timeout)

    # ---------------------------------------------------------- connecting
    def connect(self, name: str, cfg: dict) -> None:
        """Start a server and load its tools (blocking; raises on failure)."""
        self.disconnect(name)
        state = ServerState(name, dict(cfg), "connecting")
        self.servers[name] = state
        try:
            self._run(self._start(state), CONNECT_TIMEOUT + 10)
        except BaseException as exc:  # noqa: BLE001
            state.status, state.error = "error", state.error or _short_error(exc)
            raise RuntimeError(state.error) from exc

    async def _start(self, state: ServerState) -> None:
        loop = asyncio.get_running_loop()
        state.stop = asyncio.Event()
        ready = loop.create_future()
        state.task = loop.create_task(self._serve(state, ready))
        await asyncio.wait_for(ready, CONNECT_TIMEOUT)

    async def _serve(self, state: ServerState, ready: asyncio.Future) -> None:
        """Owns the server's whole lifetime (contexts must open/close in one task)."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            cfg = state.cfg
            async with AsyncExitStack() as stack:
                if cfg.get("url"):
                    try:
                        from mcp.client.streamable_http import streamablehttp_client as http_client
                    except ImportError:             # newer SDK name
                        from mcp.client.streamable_http import streamable_http_client as http_client
                    streams = await stack.enter_async_context(http_client(cfg["url"]))
                    read, write = streams[0], streams[1]
                else:
                    command = cfg.get("command", "")
                    if not command:
                        raise ValueError("No command configured for this server")
                    params = StdioServerParameters(
                        command=shutil.which(command) or command,   # finds npx.cmd etc. on Windows
                        args=list(cfg.get("args", [])), env=cfg.get("env") or None,
                        cwd=cfg.get("cwd") or None)
                    read, write = await stack.enter_async_context(stdio_client(params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                result = await session.list_tools()
                state.tools = [{"name": t.name, "description": t.description or "",
                                "schema": t.inputSchema or {}} for t in result.tools]
                state.session, state.status, state.error = session, "connected", ""
                if not ready.done():
                    ready.set_result(True)
                await state.stop.wait()
        except Exception as exc:  # noqa: BLE001
            logging.warning("MCP server %s failed: %s", state.name, exc)
            state.status, state.error = "error", _short_error(exc)
            if not ready.done():
                ready.set_exception(exc)
        finally:
            state.session = None
            if state.status == "connected":
                state.status = "stopped"

    def disconnect(self, name: str) -> None:
        state = self.servers.pop(name, None)
        if state and state.stop is not None and state.task is not None:
            try:
                self._run(self._stop(state), 15)
            except Exception:  # noqa: BLE001
                logging.exception("Error stopping MCP server %s", name)

    @staticmethod
    async def _stop(state: ServerState) -> None:
        state.stop.set()
        try:
            await asyncio.wait_for(state.task, 10)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            state.task.cancel()

    def close(self) -> None:
        for name in list(self.servers):
            self.disconnect(name)
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

    # --------------------------------------------------------------- status
    def has_connected(self) -> bool:
        return any(s.status == "connected" and s.cfg.get("enabled", True) for s in self.servers.values())

    def snapshot(self, configured: dict) -> list:
        """Rows for the Tools page: one per configured server."""
        rows = []
        for name, cfg in configured.items():
            st = self.servers.get(name)
            rows.append({
                "name": name, "enabled": cfg.get("enabled", True),
                "command": cfg.get("url") or " ".join([cfg.get("command", "")] + list(cfg.get("args", []))),
                "status": st.status if st else "idle", "error": st.error if st else "",
                "tools": len(st.tools) if st else 0})
        return rows

    # ----------------------------------------------------------------- tools
    def tool_specs(self, query: str, k: int = 8) -> list:
        """Ollama tool specs for the k tools most relevant to `query`."""
        q = _tokens(query)
        scored = []
        for st in self.servers.values():
            if st.status != "connected" or not st.cfg.get("enabled", True):
                continue
            for tool in st.tools:
                score = _score(q, tool["name"], tool["description"])
                if score > 0:
                    scored.append((score, st.name, tool))
        scored.sort(key=lambda item: -item[0])
        specs, used = [], set()
        self._alias = {}
        for _score_value, server, tool in scored[:k]:
            alias = re.sub(r"[^A-Za-z0-9_]", "_", f"{server}__{tool['name']}")[:64]
            while alias in used:
                alias = alias[:-1] + "_"
            used.add(alias)
            self._alias[alias] = (server, tool["name"])
            schema = _slim(tool["schema"]) or {"type": "object", "properties": {}}
            specs.append({"type": "function", "function": {
                "name": alias, "description": tool["description"][:300], "parameters": schema}})
        return specs

    def describe(self, alias: str) -> str:
        server, tool = self._alias.get(alias, ("?", alias))
        return f"{server} \u203a {tool}"

    def call_alias(self, alias: str, args: dict) -> str:
        """Run a tool chosen by the model (blocking)."""
        if alias not in self._alias:
            raise KeyError(f"Unknown tool '{alias}'")
        server, tool = self._alias[alias]
        state = self.servers.get(server)
        if state is None or state.status != "connected":
            raise RuntimeError(f"Server '{server}' is not connected")
        return self._run(self._call(state, tool, args), CALL_TIMEOUT + 10)

    @staticmethod
    async def _call(state: ServerState, tool: str, args: dict) -> str:
        result = await asyncio.wait_for(state.session.call_tool(tool, args), CALL_TIMEOUT)
        parts = []
        for item in result.content:
            text = getattr(item, "text", None)
            parts.append(text if text is not None else f"[{getattr(item, 'type', 'content')}]")
        text = "\n".join(parts) or "(no output)"
        return f"Error: {text}" if result.isError else text
