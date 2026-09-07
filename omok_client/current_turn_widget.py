"""Boxed current-turn indicator for the Room header."""

from __future__ import annotations

import tkinter as tk


class CurrentTurnWidget(tk.Canvas):
    WIDTH = 140
    HEIGHT = 76
    BACKGROUND = "#FFF8EA"
    BORDER = "#7B542B"

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
        self._color: str | None = None
        self.bind("<Configure>", self._on_configure)
        self._draw()

    def set_color(self, color: str | None) -> None:
        if color == self._color:
            return
        self._color = color
        self._draw()

    def _on_configure(self, _event: tk.Event[tk.Misc]) -> None:
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), self.WIDTH)
        height = max(self.winfo_height(), self.HEIGHT)
        self.create_rectangle(
            3, 3, width - 3, height - 3,
            fill=self.BACKGROUND, outline=self.BORDER, width=3,
        )
        self.create_text(
            width / 2, 19, text="CURRENT TURN", fill="#3E2B18",
            font=("TkDefaultFont", 9, "bold"),
        )
        if self._color in {"BLACK", "WHITE"}:
            self.create_oval(
                width / 2 - 15, 35, width / 2 + 15, 65,
                fill="#171717" if self._color == "BLACK" else "#F4F4F4",
                outline="#000000", width=2,
            )
        else:
            self.create_text(
                width / 2, 50, text="--", fill="#3E2B18",
                font=("TkDefaultFont", 18, "bold"),
            )
