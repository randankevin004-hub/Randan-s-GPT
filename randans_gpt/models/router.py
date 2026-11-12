"""
models/router.py
----------------
Model catalogue and the keyword-based "Auto" router.

Coding           -> qwen2.5:1.5b
Math / reasoning -> deepseek-r1:1.5b
Writing / blogs  -> gemma2:2b
General chat     -> llama3.2:1b
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    tag: str      # Ollama model tag
    label: str    # Friendly name shown in the UI


MODELS = [
    ModelInfo("llama3.2:1b", "Llama 3.2 1B"),
    ModelInfo("gemma2:2b", "Gemma 2B"),
    ModelInfo("deepseek-r1:1.5b", "DeepSeek R1 1.5B"),
    ModelInfo("qwen2.5:1.5b", "Qwen 2.5 1.5B"),
]
AUTO_LABEL = "Auto (smart routing)"
DEFAULT_MODEL = "llama3.2:1b"
LABEL_TO_TAG = {m.label: m.tag for m in MODELS}
TAG_TO_LABEL = {m.tag: m.label for m in MODELS}

def label_for(tag: str) -> str:
    """Friendly name for any Ollama tag, e.g. 'phi3:mini' -> 'Phi3 Mini'."""
    if tag in TAG_TO_LABEL:
        return TAG_TO_LABEL[tag]
    name, _, variant = tag.rsplit("/", 1)[-1].partition(":")
    words = [w[:1].upper() + w[1:] for w in re.split(r"[-_\s]+", name) if w]
    label = " ".join(words)
    if variant and variant != "latest":
        if re.fullmatch(r"\d+(\.\d+)?[bm]", variant, re.I):        # 4b -> 4B
            label += " " + variant.upper()
        elif re.fullmatch(r"[qQ]\d.*|f16|fp16|bf16", variant):       # quantisation
            label += f" ({variant})"
        else:
            label += " " + variant[:1].upper() + variant[1:]
    return label


CODE_MODEL = "qwen2.5:1.5b"
MATH_MODEL = "deepseek-r1:1.5b"
WRITING_MODEL = "gemma2:2b"
GENERAL_MODEL = "llama3.2:1b"

CODE_WORDS = [
    "code", "coding", "python", "javascript", "typescript", "java", "c++", "c#",
    "html", "css", "sql", "bash", "powershell", "function", "bug", "debug",
    "compile", "compiler", "script", "algorithm", "api", "json", "regex", "class",
    "variable", "loop", "array", "stack trace", "exception", "syntax", "github",
    "git", "react", "django", "flask", "node", "kotlin", "firebase", "program",
    "refactor", "unit test", "error", "traceback", "def", "import", "npm", "pip",
]
MATH_WORDS = [
    "solve", "calculate", "calculation", "math", "maths", "equation", "integral",
    "derivative", "algebra", "geometry", "probability", "prove", "proof", "logic",
    "puzzle", "riddle", "reasoning", "step by step", "how many", "percentage",
    "percent", "sum of", "product of", "factorial", "prime", "theorem", "fraction",
    "square root", "average", "compute", "arithmetic",
]
WRITING_WORDS = [
    "write", "blog", "article", "essay", "story", "poem", "email", "letter",
    "rewrite", "paraphrase", "caption", "post", "paragraph", "headline", "speech",
    "proofread", "summarize", "summary", "slogan", "copywriting", "newsletter",
    "product description", "cover letter", "tweet", "outline",
]


def _compile(words: list) -> re.Pattern:
    # (?<!\w) / (?!\w) behave like \b but also work for "c++" and "c#".
    return re.compile("|".join(rf"(?<!\w){re.escape(w)}(?!\w)" for w in words), re.I)


_CODE_RE, _MATH_RE, _WRITE_RE = map(_compile, (CODE_WORDS, MATH_WORDS, WRITING_WORDS))
_ARITHMETIC_RE = re.compile(r"\d+\s*[-+*/^=x]\s*\d+")
_CODE_SYNTAX_RE = re.compile(r"```|=>|\bdef \w+\(|\bfunction\s*\w*\(|#include|</?\w+>")


def classify(prompt: str) -> str:
    """Category of a prompt: 'code', 'math', 'writing' or 'general'."""
    code = len(_CODE_RE.findall(prompt)) + (2 if _CODE_SYNTAX_RE.search(prompt) else 0)
    math = len(_MATH_RE.findall(prompt)) + (2 if _ARITHMETIC_RE.search(prompt) else 0)
    writing = len(_WRITE_RE.findall(prompt))
    best = max(code, math, writing)
    if best == 0:
        return "general"
    # Ties resolve in the order: code > math > writing.
    return "code" if code == best else "math" if math == best else "writing"


DEFAULT_ROUTES = {"code": CODE_MODEL, "math": MATH_MODEL, "writing": WRITING_MODEL, "general": GENERAL_MODEL}


def route(prompt: str, mapping: dict | None = None) -> str:
    """Pick the best model tag for a prompt. `mapping` (category -> tag) overrides the defaults."""
    category = classify(prompt)
    if mapping and mapping.get(category):
        return mapping[category]
    return DEFAULT_ROUTES[category]
