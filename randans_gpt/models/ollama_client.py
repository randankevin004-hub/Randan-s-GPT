"""
models/ollama_client.py
-----------------------
Wrapper around the official `ollama` Python library.

* stream_chat() is a generator yielding text chunks as the model produces them.
* Every low-level failure is translated into a friendly OllamaError.
* DeepSeek-R1 "thinking" output is wrapped in <think>...</think> so the UI can
  show it in a dimmed style.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Iterator, Optional

import httpx
import ollama

THINK_RE = re.compile(r"<think>.*?(?:</think>|\Z)", re.DOTALL)


TOOL_NOTE_RE = re.compile(r"\n*\*(?:Using tool `[^`]*`\.\.\.|[^\n*]*can't use tools[^\n*]*)\*\n*")


def strip_think(text: str) -> str:
    """Remove reasoning blocks (not worth re-sending to the model)."""
    return THINK_RE.sub("", text).strip()


def clean_for_model(text: str) -> str:
    """Remove reasoning blocks and tool-status notes from past replies."""
    return TOOL_NOTE_RE.sub("\n", strip_think(text)).strip()


class OllamaError(Exception):
    """Base class; `user_message` is safe to show directly to the user."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class OllamaNotRunning(OllamaError):
    pass


class ModelMissing(OllamaError):
    pass


def _translate(exc: Exception, model: Optional[str] = None) -> OllamaError:
    """Map any exception raised by the library to a friendly OllamaError."""
    if isinstance(exc, OllamaError):
        return exc
    detail = str(getattr(exc, "error", "") or exc)
    if isinstance(exc, ollama.ResponseError):
        if getattr(exc, "status_code", None) == 404 or "not found" in detail.lower():
            name = model or "that model"
            return ModelMissing(
                f"The model '{name}' isn't installed yet.\n"
                f"Open a terminal and run:  `ollama pull {name}`")
        if "does not support tools" in detail.lower():
            return OllamaError("This model can't use tools. Choose Qwen 2.5, Qwen3.5 or Llama 3.2, "
                               "or turn the Tools button off.")
        return OllamaError(f"Ollama reported a problem: {detail}")
    if isinstance(exc, (ConnectionError, httpx.TransportError)) or "connect" in detail.lower():
        return OllamaNotRunning(
            "I can't reach Ollama. Please start the Ollama app "
            "(or run `ollama serve` in a terminal) and try again.")
    return OllamaError(f"Something went wrong while talking to Ollama: {detail}")


class OllamaService:
    def __init__(self, host: Optional[str] = None) -> None:
        # With host=None the library honours OLLAMA_HOST or uses localhost:11434.
        self._client = ollama.Client(host=host) if host else ollama.Client()

    def installed_models(self) -> list:
        """Tags of locally installed models. Raises OllamaError if unreachable."""
        try:
            response = self._client.list()
            names = []
            for item in response["models"]:
                name = item.get("model") or item.get("name")
                if name:
                    names.append(name)
            return names
        except Exception as exc:  # noqa: BLE001 - translated below
            raise _translate(exc) from exc

    def pull(self, model: str, on_progress, stop_event: threading.Event) -> bool:
        """Download a model. on_progress(status, completed, total, digest). False if cancelled."""
        stream = None
        try:
            stream = self._client.pull(model, stream=True)
            for chunk in stream:
                if stop_event.is_set():
                    return False
                on_progress(chunk.get("status") or "", chunk.get("completed"), chunk.get("total"), chunk.get("digest"))
            return True
        except Exception as exc:  # noqa: BLE001
            detail = str(getattr(exc, "error", "") or exc).lower()
            if "file does not exist" in detail or "manifest" in detail or isinstance(exc, ollama.ResponseError) and getattr(exc, "status_code", 0) == 404:
                raise OllamaError(f"Ollama's library has no model called '{model}'.") from exc
            if "no space" in detail or "disk" in detail:
                raise OllamaError("Not enough free disk space to download this model.") from exc
            raise _translate(exc, model) from exc
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001
                    pass

    def supports_tools(self, model: str):
        """True / False if Ollama reports tool support for `model`, None if unknown."""
        try:
            caps = self._client.show(model).get("capabilities")
            return None if caps is None else "tools" in caps
        except Exception:  # noqa: BLE001
            return None

    def stream_chat(self, model: str, messages: list,
                    stop_event: threading.Event,
                    options: Optional[dict] = None,
                    tools: Optional[list] = None, tool_runner=None) -> Iterator[str]:
        """Yield response text chunk by chunk until done or `stop_event` is set.

        With `tools` (Ollama function specs) and `tool_runner(name, args) -> str`,
        runs an agent loop: model asks for a tool -> we run it -> model continues
        (up to 6 rounds). Tool activity appears as short italic notes in the stream.
        """
        stream = None
        try:
            if tools and self.supports_tools(model) is False:
                yield "*This model can't use tools, so I'll answer without them.*\n\n"
                tools = None
            msgs = list(messages)
            for _round in range(6 if tools else 1):
                kwargs = dict(model=model, messages=msgs, stream=True,
                              options=options or {}, keep_alive="10m")
                if tools:
                    kwargs["tools"] = tools
                stream = self._client.chat(**kwargs)
                in_think, calls, text = False, [], ""
                for chunk in stream:
                    if stop_event.is_set():
                        return
                    message = chunk["message"]
                    thinking = message.get("thinking")
                    content = message.get("content") or ""
                    if thinking:                      # separate reasoning field
                        if not in_think:
                            in_think = True
                            yield "<think>"
                        yield thinking
                    if content:
                        if in_think:
                            in_think = False
                            yield "</think>"
                        text += content
                        yield content
                    if message.get("tool_calls"):
                        calls.extend(message["tool_calls"])
                if in_think:
                    yield "</think>"
                if not calls or tool_runner is None:
                    return
                msgs.append({"role": "assistant", "content": text, "tool_calls": calls})
                for call in calls:
                    fn = call["function"]
                    name, args = fn["name"], dict(fn["arguments"] or {})
                    yield f"\n\n*Using tool `{name}`...*\n\n"
                    result = tool_runner(name, args)
                    msgs.append({"role": "tool", "tool_name": name, "content": result})
        except Exception as exc:  # noqa: BLE001
            logging.exception("Ollama streaming failed")
            raise _translate(exc, model) from exc
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001
                    pass
