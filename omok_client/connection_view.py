"""Server connection progress screen."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class ConnectionView(ttk.Frame):
    """Shown until the server confirms the WebSocket connection."""

    def __init__(self, parent: tk.Misc, *, server_var: tk.StringVar,
                 on_retry: Callable[[], None],
                 on_settings: Callable[[], None]) -> None:
        super().__init__(parent, padding=30)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)
        self.columnconfigure(0, weight=1)

        ttk.Label(
            self, text="Connecting to Server", font=("TkDefaultFont", 20, "bold")
        ).grid(row=1, column=0, pady=(0, 14))
        ttk.Label(self, textvariable=server_var).grid(row=2, column=0, pady=(0, 18))
        self.retry_button = ttk.Button(self, text="Retry", command=on_retry)
        self.retry_button.grid(row=3, column=0)
        self.settings_button = tk.Button(
            self, text="⚙", command=on_settings, font=("Segoe UI Symbol", 22),
            foreground="#4B4033", background="#F4E8D0",
            activebackground="#E8D3AE", relief="flat", borderwidth=0,
            padx=10, pady=6, cursor="hand2", takefocus=True,
        )
        self.settings_button.grid(row=5, column=0, sticky="se")
