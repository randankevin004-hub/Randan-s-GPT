"""
ui/chat_view.py
---------------
ChatView   - scrollable conversation area.
MessageBubble - one message (user bubble right, AI bubble left) with a Copy
button, model label and an animated typing indicator.
"""
from __future__ import annotations

import customtkinter as ctk

from ui import theme
from ui.markdown_renderer import RichText


class MessageBubble(ctk.CTkFrame):
    def __init__(self, master, chat_view: "ChatView", role: str,
                 content: str = "", model: str | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.chat_view = chat_view
        self.role = role
        self.content = content
        self._typing = False
        self._typing_job = None
        self._typing_step = 0

        is_user = role == "user"
        bg_key = {"user": "user_bg", "error": "error_bg"}.get(role, "ai_bg")
        fg_key = {"user": "user_fg", "error": "error_fg"}.get(role, "ai_fg")
        anchor = "e" if is_user else "w"            # user right, AI left

        self.card = ctk.CTkFrame(self, fg_color=theme.duo(bg_key), corner_radius=16)
        self.card.pack(anchor=anchor, padx=4)
        self.text = RichText(self.card, bg=theme.pal(bg_key), fg=theme.pal(fg_key),
                             font_size=chat_view.font_size, on_wheel=chat_view.on_wheel)
        self.text.pack(padx=8, pady=6)

        if role != "error":
            footer = ctk.CTkFrame(self, fg_color="transparent")
            footer.pack(anchor=anchor, padx=8)
            if model and not is_user:
                ctk.CTkLabel(footer, text=model, text_color=theme.duo("muted"),
                             font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 6))
            self.copy_btn = ctk.CTkButton(
                footer, text="Copy", width=48, height=22, corner_radius=6,
                fg_color="transparent", hover_color=theme.duo("hover"),
                text_color=theme.duo("muted"), font=ctk.CTkFont(size=11),
                command=self._copy)
            self.copy_btn.pack(side="left")

        # NOTE: content is rendered by ChatView.add_message *after* packing, so
        # the Text widget is laid out when its height is measured.

    # ----------------------------------------------------------- content
    def _target_chars(self, content: str) -> int:
        max_chars = self.chat_view.max_chars(self.text)
        if self.role == "user":                       # shrink-to-fit user bubbles
            longest = max((len(line) for line in content.split("\n")), default=1)
            return min(max_chars, max(6, longest + 2))
        return max_chars

    def set_content(self, content: str, final: bool = True) -> None:
        self.content = content
        self.text.set_chars(self._target_chars(content))
        self.text.render(content, final=final)

    def relayout(self) -> None:
        """Called when the window is resized."""
        if self._typing:
            return
        self.text.set_chars(self._target_chars(self.content))
        self.text.fit_height()

    def _copy(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.content)
        self.copy_btn.configure(text="Copied!")
        self.after(1200, lambda: self.copy_btn.configure(text="Copy"))

    # -------------------------------------------------- typing indicator
    def show_typing(self) -> None:
        self._typing, self._typing_step = True, 0
        self.text.set_chars(8)
        self._tick_typing()

    def _tick_typing(self) -> None:
        if not self._typing:
            return
        frames = ("\u25CF  \u25CB  \u25CB", "\u25CB  \u25CF  \u25CB", "\u25CB  \u25CB  \u25CF")
        self.text.render(frames[self._typing_step % 3], final=False)
        self._typing_step += 1
        self._typing_job = self.after(350, self._tick_typing)

    def hide_typing(self) -> None:
        self._typing = False
        if self._typing_job is not None:
            try:
                self.after_cancel(self._typing_job)
            except Exception:  # noqa: BLE001
                pass
            self._typing_job = None

    def destroy(self) -> None:
        self.hide_typing()
        super().destroy()


class ChatView(ctk.CTkScrollableFrame):
    def __init__(self, master, font_size: int = 14) -> None:
        super().__init__(master, fg_color=theme.duo("panel"), corner_radius=0)
        self.font_size = font_size
        self.max_px = 620                      # max bubble width in pixels
        self._bubbles: list[MessageBubble] = []
        self._resize_job = None
        # Track the visible width so bubbles can wrap sensibly.
        self._parent_canvas.bind("<Configure>", self._on_canvas_configure, add="+")

    # -------------------------------------------------------- geometry
    def _on_canvas_configure(self, event) -> None:
        self.max_px = max(280, int(event.width * 0.78) - 40)
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, self._relayout)

    def _relayout(self) -> None:
        self._resize_job = None
        for bubble in self._bubbles:
            bubble.relayout()

    def max_chars(self, text_widget: RichText) -> int:
        return max(20, int(self.max_px / text_widget.char_width))

    def on_wheel(self, event):
        """Forward mouse-wheel events from the Text widgets to the canvas."""
        if event.delta:
            self._parent_canvas.yview("scroll", -int(event.delta / 6) or (-1 if event.delta > 0 else 1), "units")
        return "break"

    def is_at_bottom(self) -> bool:
        return self._parent_canvas.yview()[1] >= 0.97

    def scroll_to_bottom(self, settle: bool = False) -> None:
        """Scroll to the newest message. settle=True repeats once layout
        (Text heights, scrollregion) has caught up."""
        self.update_idletasks()
        self._parent_canvas.yview_moveto(1.0)
        if settle:
            for delay in (80, 250):
                self.after(delay, lambda: self._parent_canvas.yview_moveto(1.0))

    # --------------------------------------------------------- content
    def clear(self) -> None:
        for bubble in self._bubbles:
            bubble.destroy()
        self._bubbles.clear()
        self._parent_canvas.yview_moveto(0)

    def add_message(self, role: str, content: str, model: str | None = None,
                    typing: bool = False) -> MessageBubble:
        bubble = MessageBubble(self, self, role, content, model)
        bubble.pack(fill="x", padx=14, pady=(8, 2))
        self._bubbles.append(bubble)
        if content:
            bubble.set_content(content)
        if typing:
            bubble.show_typing()
        return bubble

    def remove_bubble(self, bubble: MessageBubble) -> None:
        if bubble in self._bubbles:
            self._bubbles.remove(bubble)
        bubble.destroy()
