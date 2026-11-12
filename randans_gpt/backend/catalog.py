"""
backend/catalog.py
------------------
Curated list of Ollama models and the logic that picks the right ones for a
PC (from backend.specs) and what the user wants to do with the app.

Sizes are approximate download sizes of the default Q4 builds.
Categories: code, math, writing, study, general, translate.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogModel:
    tag: str
    label: str
    params_b: float
    size_gb: float
    uses: tuple
    blurb: str


C = CatalogModel
CATALOG = [
    # ---- everyday / writing / study / languages
    C("gemma3:1b", "Gemma 3 1B", 1.0, 0.8, ("general", "writing", "translate"), "Tiny and quick, surprisingly multilingual"),
    C("llama3.2:1b", "Llama 3.2 1B", 1.2, 1.3, ("general",), "Very light everyday assistant"),
    C("llama3.2:3b", "Llama 3.2 3B", 3.2, 2.0, ("general", "study", "writing"), "Great all-rounder for modest PCs"),
    C("phi3:mini", "Phi-3 Mini", 3.8, 2.2, ("study", "general"), "Strong reasoning for its size"),
    C("qwen3:4b", "Qwen3 4B", 4.0, 2.6, ("study", "math", "general", "translate"), "Thinks step by step - great for learning"),
    C("gemma3:4b", "Gemma 3 4B", 4.3, 3.3, ("writing", "study", "translate", "general"), "Excellent writing and clear explanations"),
    C("llama3.1:8b", "Llama 3.1 8B", 8.0, 4.9, ("general", "writing", "study"), "Smart, fluent and well-rounded"),
    C("qwen3:8b", "Qwen3 8B", 8.2, 5.2, ("study", "math", "general", "translate"), "Deep step-by-step reasoning"),
    C("gemma2:9b", "Gemma 2 9B", 9.2, 5.4, ("writing", "general", "translate"), "Polished, natural writing"),
    C("gemma3:12b", "Gemma 3 12B", 12.2, 8.1, ("writing", "study", "translate", "general"), "Top-tier writing and explanations"),
    C("qwen3:14b", "Qwen3 14B", 14.8, 9.3, ("study", "math", "general", "translate"), "Very strong reasoning"),
    C("gemma3:27b", "Gemma 3 27B", 27.0, 17.0, ("writing", "study", "translate", "general"), "Near-premium quality"),
    # ---- coding
    C("qwen2.5-coder:1.5b", "Qwen2.5 Coder 1.5B", 1.5, 1.0, ("code",), "Light coding helper"),
    C("qwen2.5-coder:3b", "Qwen2.5 Coder 3B", 3.1, 1.9, ("code",), "Capable coder that runs on modest PCs"),
    C("qwen2.5-coder:7b", "Qwen2.5 Coder 7B", 7.6, 4.7, ("code",), "Strong code generation and debugging"),
    C("qwen2.5-coder:14b", "Qwen2.5 Coder 14B", 14.8, 9.0, ("code",), "Professional-grade coding"),
    C("qwen2.5-coder:32b", "Qwen2.5 Coder 32B", 32.8, 20.0, ("code",), "Best open coding model for big GPUs"),
    # ---- maths / reasoning
    C("deepseek-r1:1.5b", "DeepSeek R1 1.5B", 1.8, 1.1, ("math", "study"), "Small step-by-step reasoner"),
    C("deepseek-r1:7b", "DeepSeek R1 7B", 7.6, 4.7, ("math", "study"), "Serious maths and logic"),
    C("deepseek-r1:14b", "DeepSeek R1 14B", 14.8, 9.0, ("math", "study"), "Advanced reasoning"),
]
BY_TAG = {m.tag: m for m in CATALOG}

USE_CASES = [
    {"key": "code", "label": "Coding", "icon": "code", "desc": "Write, debug and explain code, build websites"},
    {"key": "study", "label": "Studying", "icon": "book", "desc": "Learn topics, summarise notes, quiz yourself"},
    {"key": "writing", "label": "Writing", "icon": "pen", "desc": "Emails, essays, blogs, marketing copy"},
    {"key": "math", "label": "Maths & reasoning", "icon": "percent", "desc": "Step-by-step problem solving and logic"},
    {"key": "general", "label": "Everyday chat", "icon": "chat", "desc": "Questions, ideas and quick answers"},
    {"key": "translate", "label": "Languages", "icon": "globe", "desc": "Translate and practise languages"},
]
USE_LABEL = {u["key"]: u["label"] for u in USE_CASES}


def capacity(specs: dict) -> dict:
    """How big a model this PC can run comfortably ('fast') or slowly but usably ('ok')."""
    ram = specs.get("ram_gb") or 8
    if specs.get("gpu_accel") and (specs.get("vram_gb") or 0) >= 4:
        vram = specs["vram_gb"]
        fast_gb = vram * 0.85                      # whole model fits in VRAM
        ok_gb = fast_gb + max(0.0, ram - 6) * 0.35  # partly offloaded to RAM
        mode, fast_params = "gpu", 99.0
        label = "Strong" if vram >= 12 else "Good"
    else:
        usable = max(0.0, ram - 4.5)               # leave room for Windows + the app
        fast_gb, ok_gb = usable * 0.6, usable * 0.7
        threads = specs.get("threads") or 4
        mode, fast_params = "cpu", (4.5 if threads >= 6 else 3.5)
        label = "Good" if ram >= 24 else "Standard" if ram >= 12 else "Entry"
    return {"mode": mode, "fast_gb": round(fast_gb, 1), "ok_gb": round(ok_gb, 1),
            "fast_params": fast_params, "ok_params": 9.5 if mode == "cpu" else 99.0, "label": label}


def speed_of(model: CatalogModel, cap: dict) -> str | None:
    """'fast', 'ok' (slower) or None (too heavy for this PC)."""
    if model.size_gb <= cap["fast_gb"] and model.params_b <= cap["fast_params"]:
        return "fast"
    if model.size_gb <= cap["ok_gb"] and model.params_b <= cap["ok_params"]:
        return "ok"
    return None


def recommend(specs: dict, uses: list, pref: str = "balanced", installed: list | None = None) -> dict:
    """Build an install plan. pref: 'speed' | 'balanced' | 'quality'."""
    installed = installed or []
    have = lambda tag: tag in installed or f"{tag}:latest" in installed  # noqa: E731
    cap = capacity(specs)
    uses = [u for u in uses if u in USE_LABEL] or ["general"]
    warnings: list = []
    fits = [(m, speed_of(m, cap)) for m in CATALOG]
    fits = [(m, s) for m, s in fits if s]
    if not fits:
        fits = [(BY_TAG["gemma3:1b"], "ok")]
        warnings.append("This PC has very little memory for AI. Smaller models will work, but expect slow answers.")

    def candidates(use: str, speeds: tuple) -> list:
        return sorted([m for m, s in fits if use in m.uses and s in speeds], key=lambda m: m.params_b)

    def best(use: str):
        fast, anyspeed = candidates(use, ("fast",)), candidates(use, ("fast", "ok"))
        pool = fast or anyspeed
        if not pool:
            pool = sorted([m for m, _ in fits], key=lambda m: m.params_b)
        if pref == "speed":
            small = [m for m in pool if m.params_b <= 3.5] or pool[:1]
            return small[-1]
        if pref == "quality":
            return (anyspeed or pool)[-1]
        return pool[-1]

    chosen: dict = {}                                  # use -> model
    for use in uses:
        chosen[use] = best(use)
    # reuse one model for several uses when it is nearly as good (saves downloads)
    reuse: dict = {}
    for use in uses:
        for other, model in list(chosen.items()):
            if other != use and use in model.uses and model.params_b >= 0.7 * chosen[use].params_b:
                reuse[use] = model
                break
    for use, model in reuse.items():
        if chosen[use] is not model:
            chosen[use] = model

    speed_by_tag = {m.tag: s for m, s in fits}
    picks, seen = [], {}
    for use in uses:
        m = chosen[use]
        if m.tag in seen:
            seen[m.tag]["also"].append(USE_LABEL[use])
            continue
        entry = {"use": use, "use_label": USE_LABEL[use], "tag": m.tag, "label": m.label, "size_gb": m.size_gb,
                 "params_b": m.params_b, "speed": speed_by_tag.get(m.tag, "ok"), "blurb": m.blurb,
                 "installed": have(m.tag), "also": []}
        seen[m.tag] = entry
        picks.append(entry)

    general = chosen.get("general") or chosen.get("writing") or chosen.get("study") or next(iter(chosen.values()))
    route_map = {"general": general.tag}
    for key in ("code", "math", "writing", "study", "translate"):
        route_map[key] = (chosen.get(key) or (chosen.get("writing") if key in ("translate",) else None) or general).tag
    total = round(sum(p["size_gb"] for p in picks if not p["installed"]), 1)
    disk = specs.get("disk_free_gb")
    disk_ok = disk is None or disk >= total + 2
    if not disk_ok:
        warnings.append(f"You need about {total + 2:.0f} GB free for these downloads but only {disk:.0f} GB is available.")
    if cap["mode"] == "cpu" and specs.get("gpu_name") and not specs.get("gpu_accel"):
        warnings.append("Your graphics card can't speed up Ollama here, so models run on the CPU.")
    return {"capacity": cap, "picks": picks, "route_map": route_map, "default_model": general.tag,
            "total_gb": total, "disk_free_gb": disk, "disk_ok": disk_ok, "warnings": warnings}
