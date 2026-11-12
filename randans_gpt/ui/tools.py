"""
ui/tools.py
-----------
Left-rail "tools" (each one = a model + a system-prompt personality) and the
quick prompt templates behind the note button.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    key: str
    label: str
    icon: str
    model: str          # Ollama tag this tool prefers
    prompt: str         # extra system instructions while the tool is active

    @property
    def category(self) -> str:
        """Which model category (see models.router / backend.catalog) this tool should use."""
        return TOOL_CATEGORY.get(self.key, "general")


TOOL_CATEGORY = {"code": "code", "data": "code", "math": "math", "write": "writing", "email": "writing",
                 "translate": "translate", "explain": "study", "study": "study",
                 "summarize": "general", "brainstorm": "general"}

TOOLS = [
    Tool("code", "Code assistant", "code", "qwen2.5:1.5b",
         "You are an expert programmer. Give correct, minimal, well-commented code in fenced "
         "code blocks with a language tag, then a short explanation."),
    Tool("math", "Math & logic", "grid", "deepseek-r1:1.5b",
         "You are a careful maths and logic tutor. Solve step by step, double-check the result "
         "and state the final answer clearly."),
    Tool("write", "Writing studio", "pen", "gemma2:2b",
         "You are a skilled writer and editor. Produce polished, engaging text that matches the "
         "requested tone and format."),
    Tool("translate", "Translator", "globe", "gemma2:2b",
         "You are a translator. Translate the user's text accurately. If no target language is "
         "given, translate between English and Swahili. Output only the translation unless asked."),
    Tool("summarize", "Summarizer", "lines", "llama3.2:1b",
         "Summarize the user's text concisely: a one-line TL;DR followed by short bullet points."),
    Tool("brainstorm", "Brainstorm", "bulb", "llama3.2:1b",
         "Brainstorm creative, practical ideas as a numbered list with a one-line rationale each."),
]

MORE_TOOLS = [
    Tool("explain", "Explain simply", "sparkle", "llama3.2:1b",
         "Explain things simply, as if to a curious 12-year-old, using everyday examples."),
    Tool("email", "Email drafter", "mail", "gemma2:2b",
         "Draft clear, polite, professional emails with a subject line."),
    Tool("study", "Study buddy", "book", "llama3.2:1b",
         "Act as a study buddy: explain concepts, then quiz the user with 3 short questions."),
    Tool("data", "Data helper", "bars", "qwen2.5:1.5b",
         "Help with data analysis, spreadsheets formulas, SQL and charts. Be precise."),
]

ALL_TOOLS = {t.key: t for t in TOOLS + MORE_TOOLS}

TEMPLATES = [
    ("Summarize this", "Summarize the following text in 5 bullet points:\n\n"),
    ("Explain like I'm 12", "Explain this like I'm 12 years old: "),
    ("Fix this code", "Find and fix the bug in this code, and explain what was wrong:\n\n"),
    ("Write a professional email", "Write a professional email about: "),
    ("Brainstorm ideas", "Give me 10 creative ideas for: "),
    ("Translate to Swahili", "Translate to Swahili: "),
    ("Pros and cons", "List the pros and cons of: "),
]
