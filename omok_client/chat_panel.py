"""Room chat panel: server-echoed message log plus a single-line composer."""

from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable

from .chat import MAX_CHAT_TEXT_LENGTH
from .state import ChatMessage

SendCallback = Callable[[str], bool]


class ChatPanel(ttk.Frame):
    """Displays ``AppState.chat_messages`` and forwards composed text to ``on_send``.

    The panel never appends a message on its own. The owner re-renders from the
    authoritative state after the server echoes ``chat_message`` back, so the
    log stays identical for every member of the room.
    """

    def __init__(self, master: tk.Misc, on_send: SendCallback) -> None:
        super().__init__(master, padding=(8, 4))
        self._on_send = on_send
        self._rendered_count = 0
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Chat", font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        log_frame = ttk.Frame(self)
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(
            log_frame,
            width=30,
            height=8,
            wrap="word",
            state="disabled",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#C9B79A",
            font=("TkDefaultFont", 10),
        )
        self.log.tag_configure("time", foreground="#8A7B66")
        self.log.tag_configure("nickname", font=("TkDefaultFont", 10, "bold"))
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        composer = ttk.Frame(self)
        composer.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        composer.columnconfigure(0, weight=1)
        self.entry_var = tk.StringVar()
        self.entry = ttk.Entry(composer, textvariable=self.entry_var)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", self._submit)
        self.send_button = ttk.Button(composer, text="Send", command=self._submit)
        self.send_button.grid(row=0, column=1, padx=(6, 0))
        self.set_enabled(False)

    def set_messages(self, messages: Iterable[ChatMessage]) -> None:
        items = list(messages)
        if self._rendered_count > len(items):
            self.clear()
        self.log.configure(state="normal")
        for message in items[self._rendered_count:]:
            self._insert(message)
        self.log.configure(state="disabled")
        self._rendered_count = len(items)
        self.log.see("end")

    def clear(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self._rendered_count = 0
        self.entry_var.set("")

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.entry.configure(state=state)
        self.send_button.configure(state=state)

    def message_count(self) -> int:
        return self._rendered_count

    def _submit(self, _event: object = None) -> None:
        if str(self.entry["state"]) == "disabled":
            return
        text = self.entry_var.get()
        if self._on_send(text):
            self.entry_var.set("")

    def _insert(self, message: ChatMessage) -> None:
        clock = datetime.fromtimestamp(message.sent_at_unix_ms / 1000).strftime("%H:%M")
        self.log.insert("end", f"{clock} ", ("time",))
        self.log.insert("end", f"{message.nickname}", ("nickname",))
        self.log.insert("end", f": {message.text[:MAX_CHAT_TEXT_LENGTH]}\n")
