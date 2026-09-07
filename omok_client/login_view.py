"""Unauthenticated login screen layout."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class LoginView(ttk.Frame):
    """Login form only; authentication behavior belongs to the application."""

    def __init__(self, parent: tk.Misc, *, account_id_var: tk.StringVar,
                 password_var: tk.StringVar, auto_login_var: tk.BooleanVar,
                 on_login: Callable[[], None],
                 on_create_account: Callable[[], None],
                 on_settings: Callable[[], None]) -> None:
        super().__init__(parent, padding=30)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(5, weight=1)
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Login", font=("TkDefaultFont", 20, "bold")).grid(
            row=1, column=0, pady=(0, 24)
        )
        form = ttk.Frame(self)
        form.grid(row=2, column=0)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Account ID", anchor="e", width=14).grid(
            row=0, column=0, padx=(0, 10), pady=6, sticky="e"
        )
        self.account_id_entry = ttk.Entry(form, textvariable=account_id_var, width=28)
        self.account_id_entry.grid(row=0, column=1, pady=6, sticky="ew")
        ttk.Label(form, text="Password", anchor="e", width=14).grid(
            row=1, column=0, padx=(0, 10), pady=6, sticky="e"
        )
        self.password_entry = ttk.Entry(
            form, textvariable=password_var, width=28, show="*"
        )
        self.password_entry.grid(row=1, column=1, pady=6, sticky="ew")
        self.auto_login_check = ttk.Checkbutton(
            form, text="Auto Login", variable=auto_login_var
        )
        self.auto_login_check.grid(row=2, column=1, pady=(6, 12), sticky="w")

        self.login_button = ttk.Button(
            self, text="Login", command=on_login, padding=(42, 12)
        )
        self.login_button.grid(row=3, column=0, pady=(8, 22))
        create_row = ttk.Frame(self)
        create_row.grid(row=4, column=0)
        ttk.Label(create_row, text="No account?").pack(side="left", padx=(0, 8))
        self.create_account_button = ttk.Button(
            create_row, text="Create Account", command=on_create_account
        )
        self.create_account_button.pack(side="left")

        self.settings_button = tk.Button(
            self, text="⚙", command=on_settings, font=("Segoe UI Symbol", 22),
            foreground="#4B4033", background="#F4E8D0",
            activebackground="#E8D3AE", relief="flat", borderwidth=0,
            padx=10, pady=6, cursor="hand2", takefocus=True,
        )
        self.settings_button.grid(row=6, column=0, sticky="se")

        self.account_id_entry.bind("<Return>", lambda _event: on_login())
        self.password_entry.bind("<Return>", lambda _event: on_login())
