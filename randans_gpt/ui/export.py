"""
ui/export.py
------------
Export a conversation to a plain-text or PDF file.
PDF uses the Latin-1 base fonts of reportlab, so characters outside Latin-1
(e.g. emoji) are replaced with '?'.
"""
from __future__ import annotations

import re
from datetime import datetime
from xml.sax.saxutils import escape

from models.ollama_client import strip_think


def _speaker(message: dict) -> str:
    if message["role"] == "user":
        return "You"
    return f"Randan's GPT ({message['model']})" if message.get("model") else "Randan's GPT"


def export_txt(path: str, title: str, messages: list) -> None:
    lines = [f"Randan's GPT - {title}",
             f"Exported: {datetime.now():%Y-%m-%d %H:%M}", "=" * 60, ""]
    for m in messages:
        lines.append(f"[{_speaker(m)}]  {m['created_at']}")
        lines.append(strip_think(m["content"]) or m["content"])
        lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def _pdf_text(text: str) -> str:
    """Escape for reportlab Paragraph, keeping line breaks and indentation."""
    text = text.encode("latin-1", "replace").decode("latin-1")
    out = []
    for line in text.split("\n"):
        line = escape(line)
        line = re.sub(r"^( +)", lambda m: "&nbsp;" * len(m.group(1)), line)
        out.append(line)
    return "<br/>".join(out)


def export_pdf(path: str, title: str, messages: list) -> None:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise RuntimeError("PDF export needs the 'reportlab' package. "
                           "Run: pip install reportlab") from exc

    styles = getSampleStyleSheet()
    who = ParagraphStyle("who", parent=styles["Heading4"], spaceBefore=8, spaceAfter=2)
    body = ParagraphStyle("body", parent=styles["BodyText"], leading=14)
    doc = SimpleDocTemplate(path, pagesize=A4, title=title,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    story = [Paragraph(_pdf_text(f"Randan's GPT - {title}"), styles["Title"]),
             Paragraph(f"Exported {datetime.now():%Y-%m-%d %H:%M}", styles["Normal"]),
             Spacer(1, 8)]
    for m in messages:
        story.append(Paragraph(_pdf_text(f"{_speaker(m)}  -  {m['created_at']}"), who))
        story.append(Paragraph(_pdf_text(strip_think(m["content"]) or m["content"]), body))
    doc.build(story)
