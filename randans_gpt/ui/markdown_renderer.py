"""
ui/markdown_renderer.py
-----------------------
RichText: a read-only tkinter Text widget that renders a practical subset of
Markdown (headings, bold, italic, inline code, bullet/numbered lists and
fenced code blocks with Pygments syntax highlighting) plus DeepSeek-style
<think>...</think> reasoning blocks.

It is re-rendered from scratch on every streamed update, which is fast enough
for small local models and keeps the parser trivially simple/robust.
"""
from __future__ import annotations

import re
import tkinter as tk
from functools import lru_cache
from tkinter import font as tkfont

from pygments import lex
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

from ui import theme

THINK_RE = re.compile(r"<think>(.*?)(?:</think>|\Z)", re.DOTALL)
INLINE_RE = re.compile(r"(\*\*(?!\s).+?(?<!\s)\*\*|`[^`\n]+`|\*(?!\s)[^*\n]+?(?<!\s)\*)")
HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")
BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
NUMBER_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")

SYNTAX_TAGS = ("syn_keyword", "syn_string", "syn_comment", "syn_number",
               "syn_func", "syn_class", "syn_op", "syn_builtin")


def _tag_for(ttype) -> str | None:
    """Map a Pygments token type to one of our colour tags."""
    if ttype in Token.Comment:
        return "syn_comment"
    if ttype in Token.Keyword:
        return "syn_keyword"
    if ttype in Token.Literal.String:
        return "syn_string"
    if ttype in Token.Literal.Number:
        return "syn_number"
    if ttype in Token.Name.Function or ttype in Token.Name.Decorator:
        return "syn_func"
    if ttype in Token.Name.Class:
        return "syn_class"
    if ttype in Token.Name.Builtin:
        return "syn_builtin"
    if ttype in Token.Operator:
        return "syn_op"
    return None


@lru_cache(maxsize=128)
def _highlight(lang: str, code: str) -> tuple:
    """Tokenise code -> ((tag_or_None, text), ...). Cached for streaming."""
    try:
        lexer = get_lexer_by_name(lang) if lang else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()
    try:
        return tuple((_tag_for(t), v) for t, v in lex(code, lexer))
    except Exception:  # noqa: BLE001 - never let highlighting break rendering
        return ((None, code + "\n"),)


class RichText(tk.Text):
    def __init__(self, master, *, bg: str, fg: str, font_size: int = 14, on_wheel=None):
        super().__init__(
            master, wrap="word", bg=bg, fg=fg, relief="flat", bd=0,
            highlightthickness=0, padx=10, pady=6, width=40, height=1,
            state="disabled", insertwidth=0, takefocus=0, spacing3=2,
            selectbackground=theme.pal("accent"), inactiveselectbackground=theme.pal("accent"),
        )
        self._final = True
        self._prev_blank = False
        self._copy_buttons: list = []
        self._make_fonts(font_size)
        self._configure_tags()
        if on_wheel:
            self.bind("<MouseWheel>", on_wheel)

    # ------------------------------------------------------------- setup
    def _make_fonts(self, size: int) -> None:
        fam = theme.FONT_FAMILY
        self.f_base = tkfont.Font(family=fam, size=size)
        self.f_bold = tkfont.Font(family=fam, size=size, weight="bold")
        self.f_italic = tkfont.Font(family=fam, size=size, slant="italic")
        self.f_code = tkfont.Font(family=theme.CODE_FONT, size=max(size - 1, 8))
        self.f_small = tkfont.Font(family=theme.CODE_FONT, size=max(size - 3, 8))
        self.f_h = {
            1: tkfont.Font(family=fam, size=size + 6, weight="bold"),
            2: tkfont.Font(family=fam, size=size + 4, weight="bold"),
            3: tkfont.Font(family=fam, size=size + 2, weight="bold"),
        }
        self.configure(font=self.f_base)

    def _configure_tags(self) -> None:
        p, tag = theme.pal, self.tag_configure
        tag("bold", font=self.f_bold)
        tag("italic", font=self.f_italic)
        tag("code_inline", font=self.f_code, background=p("code_bg"), foreground=p("code_fg"))
        tag("codeblock", font=self.f_code, background=p("code_bg"), foreground=p("code_fg"))
        tag("codelang", font=self.f_small, background=p("code_bg"), foreground=p("muted"))
        for name in SYNTAX_TAGS:                 # created last => highest priority
            tag(name, foreground=p(name))
        for level, font in self.f_h.items():
            tag(f"h{level}", font=font, spacing1=6)
        tag("bullet", lmargin1=8, lmargin2=26)
        tag("think", font=self.f_italic, foreground=p("think_fg"), lmargin1=8, lmargin2=8)
        tag("thinklabel", font=self.f_bold, foreground=p("muted"))

    # ------------------------------------------------------------ sizing
    @property
    def char_width(self) -> int:
        return max(1, self.f_base.measure("0"))

    def set_chars(self, chars: int) -> None:
        self.configure(width=max(4, int(chars)))

    def fit_height(self, retries: int = 3) -> None:
        """Resize the widget so all text is visible (no inner scrolling).

        Display-line counts are only correct once the widget has been laid
        out. If it hasn't yet, use the logical line count as a provisional
        height and refine a moment later.
        """
        self.update_idletasks()
        if retries > 0 and self.winfo_width() < self.winfo_reqwidth() - 4:
            self.configure(height=max(1, int(self.index("end-1c").split(".")[0])))
            self.after(40, lambda: self._refit(retries - 1))
            return
        try:
            result = self.count("1.0", "end", "displaylines")
            if isinstance(result, (tuple, list)):
                result = result[0] if result else 1
            lines = int(result or 1)
        except (tk.TclError, ValueError, TypeError):
            lines = int(self.index("end-1c").split(".")[0])
        self.configure(height=max(1, lines))

    def _refit(self, retries: int) -> None:
        try:
            self.fit_height(retries)
        except tk.TclError:            # widget destroyed meanwhile
            pass

    # --------------------------------------------------------- rendering
    def render(self, text: str, final: bool = True) -> None:
        """Replace the contents with `text` rendered as Markdown.

        final=False is used while streaming (skips the per-code-block Copy
        buttons so we don't create/destroy widgets 20 times a second).
        """
        self._final = final
        self._prev_blank = False
        self.configure(state="normal")
        for btn in self._copy_buttons:
            btn.destroy()
        self._copy_buttons.clear()
        self.delete("1.0", "end")

        pos = 0
        for match in THINK_RE.finditer(text):
            self._markdown(text[pos:match.start()])
            self._think(match.group(1))
            pos = match.end()
        self._markdown(text[pos:])

        while self.index("end-1c") != "1.0" and self.get("end-2c", "end-1c") == "\n":
            self.delete("end-2c", "end-1c")          # drop trailing blank lines
        self.configure(state="disabled")
        self.fit_height()

    def _markdown(self, text: str) -> None:
        if not text.strip():
            return
        in_code, lang, buf = False, "", []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("```"):
                if in_code:
                    self._code_block(lang, "\n".join(buf))
                    in_code, buf = False, []
                else:
                    in_code = True
                    parts = stripped[3:].strip().split()
                    lang = parts[0].lower() if parts else ""
                continue
            if in_code:
                buf.append(line)
            else:
                self._line(line)
        if in_code:                                   # unclosed fence (streaming)
            self._code_block(lang, "\n".join(buf))

    def _line(self, line: str) -> None:
        if not line.strip():
            if not self._prev_blank and self.index("end-1c") != "1.0":
                self.insert("end", "\n")
            self._prev_blank = True
            return
        self._prev_blank = False
        if m := HEADING_RE.match(line):
            self._inline(m.group(2), (f"h{len(m.group(1))}",))
        elif m := BULLET_RE.match(line):
            self.insert("end", "\u2022  ", ("bullet",))
            self._inline(m.group(1), ("bullet",))
        elif m := NUMBER_RE.match(line):
            self.insert("end", f"{m.group(1)}.  ", ("bullet",))
            self._inline(m.group(2), ("bullet",))
        else:
            self._inline(line)
        self.insert("end", "\n")

    def _inline(self, text: str, base: tuple = ()) -> None:
        """Insert text handling **bold**, *italic* and `code`."""
        for i, part in enumerate(INLINE_RE.split(text)):
            if not part:
                continue
            if i % 2 == 0:                            # plain text between matches
                self.insert("end", part, base)
            elif part.startswith("**"):
                self.insert("end", part[2:-2], base + ("bold",))
            elif part.startswith("`"):
                self.insert("end", part[1:-1], base + ("code_inline",))
            else:
                self.insert("end", part[1:-1], base + ("italic",))

    def _think(self, content: str) -> None:
        self._prev_blank = False
        self.insert("end", "Thinking\u2026\n", ("thinklabel",))
        body = content.strip("\n")
        if body.strip():
            self.insert("end", body + "\n\n", ("think",))

    def _code_block(self, lang: str, code: str) -> None:
        self._prev_blank = False
        start = self.index("end-1c")
        self.insert("end", f" {lang or 'code'}  ")
        if self._final:
            btn = tk.Button(
                self, text="Copy code", font=self.f_small, relief="flat", bd=0,
                padx=6, pady=0, cursor="hand2", bg=theme.pal("accent"), fg="#ffffff",
                activebackground=theme.pal("accent_hover"), activeforeground="#ffffff",
            )
            btn.configure(command=lambda b=btn, c=code: self._copy(b, c))
            self.window_create("end", window=btn, padx=2)
            self._copy_buttons.append(btn)
        self.insert("end", "\n")
        self.tag_add("codelang", start, "end-1c")

        tokens = _highlight(lang, code)
        for tag, value in tokens:
            self.insert("end", value, ("codeblock", tag) if tag else ("codeblock",))
        if not tokens or not tokens[-1][1].endswith("\n"):
            self.insert("end", "\n", ("codeblock",))

    def _copy(self, button: tk.Button, code: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(code)
        button.configure(text="Copied!")
        self.after(1500, lambda: self._reset_button(button))

    @staticmethod
    def _reset_button(button: tk.Button) -> None:
        try:
            button.configure(text="Copy code")
        except tk.TclError:           # button destroyed by a re-render
            pass
