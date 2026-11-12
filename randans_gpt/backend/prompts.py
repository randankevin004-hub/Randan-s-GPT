"""Prompts and message helpers shared by the HTML interface and the classic Tk interface."""
from __future__ import annotations

import re

SYSTEM_PROMPT = (
    "You are Randan's GPT, a friendly, concise AI assistant running locally on the "
    "user's Windows laptop. Answer accurately and clearly. Use Markdown, and put "
    "code in fenced code blocks with a language tag."
)
REASONING_PROMPT = "Think through the problem step by step before giving the final answer."
RESEARCH_PROMPT = ("Act as a research analyst. Write a thorough, well-structured report: a short overview, "
                   "key findings as headed sections, pros and cons or trade-offs where relevant, caveats "
                   "(say clearly when you are unsure - you have no internet access), and a brief conclusion.")
REASONING_MODEL = "deepseek-r1:1.5b"

ATTACH_RE = re.compile(r"\n*\[\[ATTACHMENT:(.*?)\]\]\n(.*?)\n\[\[/ATTACHMENT\]\]", re.DOTALL)
MAX_ATTACH_CHARS = 12000


def display_text(content: str) -> str:
    """Collapse attachment blocks for display in a chat bubble."""
    return ATTACH_RE.sub(lambda m: f"\n\n(attached file: {m.group(1)})", content).strip()


def model_text(content: str) -> str:
    """Expand attachment blocks into a form the model understands."""
    return ATTACH_RE.sub(lambda m: f"\n\nAttached file '{m.group(1)}':\n```\n{m.group(2)}\n```", content)
