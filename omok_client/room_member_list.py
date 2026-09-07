"""Scrollable Player and Observer list for a Room."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable

from .state import RoomMember


class RoomMemberList(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(8, 4))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        ttk.Label(self, text="Players", font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        self.players = ttk.Treeview(
            self, columns=("nickname", "color", "ready"), show="headings", height=2
        )
        self.players.heading("nickname", text="Nickname")
        self.players.heading("color", text="Color")
        self.players.heading("ready", text="Ready")
        self.players.column("nickname", width=105, anchor="w")
        self.players.column("color", width=55, anchor="center")
        self.players.column("ready", width=45, anchor="center")
        self.players.grid(row=1, column=0, sticky="ew")

        self.observer_title = ttk.Label(
            self, text="Observers (0)", font=("TkDefaultFont", 11, "bold")
        )
        self.observer_title.grid(row=2, column=0, sticky="w", pady=(12, 4))
        observer_frame = ttk.Frame(self)
        observer_frame.grid(row=3, column=0, sticky="nsew")
        observer_frame.rowconfigure(0, weight=1)
        observer_frame.columnconfigure(0, weight=1)
        self.observers = ttk.Treeview(
            observer_frame, columns=("nickname",), show="headings"
        )
        self.observers.heading("nickname", text="Nickname")
        self.observers.column("nickname", width=205, anchor="w")
        scrollbar = ttk.Scrollbar(
            observer_frame, orient="vertical", command=self.observers.yview
        )
        self.observers.configure(yscrollcommand=scrollbar.set)
        self.observers.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    def set_members(
        self,
        players: Iterable[RoomMember],
        observers: Iterable[RoomMember],
    ) -> None:
        player_items = list(players)
        observer_items = list(observers)
        self._clear(self.players)
        self._clear(self.observers)
        for member in player_items:
            self.players.insert(
                "", "end", values=(member.nickname, member.color, "✓" if member.ready else "")
            )
        for member in observer_items:
            self.observers.insert("", "end", values=(member.nickname,))
        self.observer_title.configure(text=f"Observers ({len(observer_items)})")

    @staticmethod
    def _clear(tree: ttk.Treeview) -> None:
        children = tree.get_children()
        if children:
            tree.delete(*children)
