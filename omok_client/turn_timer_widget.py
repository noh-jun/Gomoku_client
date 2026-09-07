"""Canvas widget dedicated to rendering the turn countdown."""

from __future__ import annotations

import tkinter as tk


class TurnTimerWidget(tk.Canvas):
    """Draw a boxed timer value with a compact title and warning state."""

    WIDTH = 140
    HEIGHT = 76
    BACKGROUND = "#FFF8EA"
    NORMAL_BORDER = "#7B542B"
    NORMAL_TEXT = "#3E2B18"
    WARNING_BORDER = "#C62828"
    WARNING_TEXT = "#C62828"

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(
            master,
            width=self.WIDTH,
            height=self.HEIGHT,
            background=self.BACKGROUND,
            highlightthickness=0,
            borderwidth=0,
            takefocus=False,
        )
        self._text = "--"
        self._warning = False
        self.bind("<Configure>", self._on_configure)
        self._draw()

    def set_display(self, text: str, warning: bool = False) -> None:
        if text == self._text and warning == self._warning:
            return
        self._text = text
        self._warning = warning
        self._draw()

    def clear(self) -> None:
        self.set_display("--")

    def _on_configure(self, _event: tk.Event[tk.Misc]) -> None:
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), self.WIDTH)
        height = max(self.winfo_height(), self.HEIGHT)
        border = self.WARNING_BORDER if self._warning else self.NORMAL_BORDER
        value_color = self.WARNING_TEXT if self._warning else self.NORMAL_TEXT

        self.create_rectangle(
            3,
            3,
            width - 3,
            height - 3,
            fill=self.BACKGROUND,
            outline=border,
            width=3,
        )
        self.create_text(
            width / 2,
            19,
            text="TURN TIME",
            fill=border,
            font=("TkDefaultFont", 9, "bold"),
        )
        self.create_text(
            width / 2,
            50,
            text=self._text,
            fill=value_color,
            font=("TkDefaultFont", 24, "bold"),
        )
