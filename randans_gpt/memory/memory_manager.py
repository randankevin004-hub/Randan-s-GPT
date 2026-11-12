"""
memory/memory_manager.py
------------------------
A deliberately simple long-term memory:

  "Remember that I'm building Podchain."  -> stored in SQLite
  "What do you know about me?"            -> memories listed back
  "Forget everything"                     -> memories cleared

Memory commands are answered locally (instantly, no model call). Stored facts
are also injected into the system prompt so the model can use them.
"""
from __future__ import annotations

import re
from typing import Optional

from database.db import Database

# "remember that ...", "remember: ...", or "remember I/my/we ..."
REMEMBER_RE = re.compile(
    r"^\s*(?:please\s+)?remember\s*(?:that\b|:)\s*(.+)$"
    r"|^\s*(?:please\s+)?remember\s+((?:i|i'm|im|i am|i've|my|we|our)\b.+)$",
    re.IGNORECASE | re.DOTALL,
)
RECALL_RES = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"what do you (?:know|remember) about me",
        r"what(?:'s| is) in your memory",
        r"what have i told you",
        r"show (?:me )?(?:my |your )?memor(?:y|ies)",
    )
]
FORGET_RE = re.compile(
    r"^\s*(?:please\s+)?(?:forget everything|forget all(?: memor(?:y|ies))?|"
    r"clear (?:my |your |all )?memor(?:y|ies))",
    re.IGNORECASE,
)


class MemoryManager:
    def __init__(self, db: Database) -> None:
        self.db = db

    def handle(self, text: str) -> Optional[str]:
        """Return a reply if `text` is a memory command, otherwise None."""
        if FORGET_RE.match(text):
            count = self.db.clear_memories()
            return ("Done - I've cleared everything I had remembered about you."
                    if count else "I don't have any saved memories yet.")

        match = REMEMBER_RE.match(text)
        if match:
            fact = (match.group(1) or match.group(2) or "").strip()
            if fact:
                added = self.db.add_memory(fact)
                return (f'Got it! I\'ll remember: "{fact}"' if added
                        else "I already have that saved.")

        if any(p.search(text) for p in RECALL_RES):
            items = self.db.list_memories()
            if not items:
                return ("I don't have anything saved about you yet. "
                        'Try telling me something with "Remember that ...".')
            lines = "\n".join(f"- {m['content']}" for m in items)
            return f"Here's what I know about you:\n\n{lines}"
        return None

    def context_block(self) -> str:
        """Text appended to the system prompt so the model can use memories."""
        items = self.db.list_memories()
        if not items:
            return ""
        lines = "\n".join(f"- {m['content']}" for m in items)
        return f"Facts the user asked you to remember:\n{lines}"
