"""Account creation screen layout."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class CreateAccountView(ttk.Frame):
    """Account form only; validation and networking belong elsewhere."""

    def __init__(self, parent: tk.Misc, *, account_id_var: tk.StringVar,
                 password_var: tk.StringVar,
                 password_confirm_var: tk.StringVar,
                 nickname_var: tk.StringVar,
                 on_create: Callable[[], None],
                 on_back: Callable[[], None]) -> None:
        super().__init__(parent, padding=30)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)
        self.columnconfigure(0, weight=1)

        ttk.Label(
            self, text="Create Account", font=("TkDefaultFont", 20, "bold")
        ).grid(row=1, column=0, pady=(0, 24))
        form = ttk.Frame(self)
        form.grid(row=2, column=0)
        form.columnconfigure(1, weight=1)
        fields = (
            ("Account ID", account_id_var, False),
            ("Password", password_var, True),
            ("Confirm Password", password_confirm_var, True),
            ("Nickname", nickname_var, False),
        )
        self.entries: list[ttk.Entry] = []
        for row, (label, variable, hidden) in enumerate(fields):
            ttk.Label(form, text=label, anchor="e", width=18).grid(
                row=row, column=0, padx=(0, 10), pady=6, sticky="e"
            )
            entry = ttk.Entry(
                form, textvariable=variable, width=28,
                show="*" if hidden else "",
            )
            entry.grid(row=row, column=1, pady=6, sticky="ew")
            self.entries.append(entry)

        buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, pady=(24, 0))
        self.back_button = ttk.Button(buttons, text="Back", command=on_back)
        self.back_button.pack(side="left", padx=6)
        self.create_button = ttk.Button(
            buttons, text="Create Account", command=on_create
        )
        self.create_button.pack(side="left", padx=6)
