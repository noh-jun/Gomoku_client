from __future__ import annotations

import logging
from queue import Empty, Queue
import tkinter as tk
from tkinter import ttk

from .board import BoardGeometry
from .network import NetworkClient, NetworkEvent
from .state import AppState, BLACK, WHITE

LOGGER = logging.getLogger(__name__)
INITIAL_CANVAS_SIZE = 780
RESIZE_DEBOUNCE_MS = 40


class OmokApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Online Omok")
        self.root.geometry("860x950")
        self.root.minsize(620, 720)
        self.state = AppState()
        self.events: Queue[NetworkEvent] = Queue()
        self.network = NetworkClient(self.events)
        self._restart_pending = False
        self._closing = False
        self._resize_after_id: str | None = None

        self.server_var = tk.StringVar(value="ws://127.0.0.1:8000")
        self.room_var = tk.StringVar(value="abc123")
        self.you_var = tk.StringVar(value="-")
        self.turn_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="Disconnected")
        self.settings_var = tk.StringVar(value="Board: 15 x 15 / Win: 5")
        self.message_var = tk.StringVar(value="Enter a room and connect.")

        self._build_ui()
        self._draw_board()
        self._render_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(50, self._poll_network_events)

    def _build_ui(self) -> None:
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer = ttk.Frame(self.root, padding=10)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(2, weight=1)
        outer.columnconfigure(0, weight=1)

        connection = ttk.LabelFrame(outer, text="Connection", padding=7)
        connection.grid(row=0, column=0, sticky="ew")
        connection.columnconfigure(1, weight=1)
        ttk.Label(connection, text="Server:").grid(row=0, column=0, sticky="w")
        self.server_entry = ttk.Entry(connection, textvariable=self.server_var, width=34)
        self.server_entry.grid(row=0, column=1, padx=(5, 10), sticky="ew")
        ttk.Label(connection, text="Room:").grid(row=0, column=2, sticky="w")
        self.room_entry = ttk.Entry(connection, textvariable=self.room_var, width=15)
        self.room_entry.grid(row=0, column=3, padx=5)
        self.connect_button = ttk.Button(connection, text="Connect", command=self._connect)
        self.connect_button.grid(row=0, column=4, padx=(5, 0))

        info = ttk.Frame(outer, padding=(0, 7))
        info.grid(row=1, column=0, sticky="ew")
        ttk.Label(info, text="You:").grid(row=0, column=0)
        ttk.Label(info, textvariable=self.you_var, width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(info, text="Turn:").grid(row=0, column=2)
        ttk.Label(info, textvariable=self.turn_var, width=8).grid(row=0, column=3, sticky="w")
        ttk.Label(info, text="Status:").grid(row=0, column=4)
        ttk.Label(info, textvariable=self.status_var, width=13).grid(row=0, column=5, sticky="w")
        ttk.Label(info, textvariable=self.settings_var).grid(row=0, column=6, padx=(12, 0), sticky="e")
        info.columnconfigure(6, weight=1)

        self.canvas = tk.Canvas(
            outer,
            width=INITIAL_CANVAS_SIZE,
            height=INITIAL_CANVAS_SIZE,
            background="#D9A85C",
            highlightthickness=1,
            highlightbackground="#7B542B",
        )
        self.canvas.grid(row=2, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_board_click)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        footer = ttk.Frame(outer, padding=(0, 7, 0, 0))
        footer.grid(row=3, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.message_var).grid(row=0, column=0, sticky="w")
        footer.columnconfigure(0, weight=1)
        self.restart_button = ttk.Button(footer, text="Restart", command=self._request_restart)
        self.restart_button.grid(row=0, column=1)

    def _connect(self) -> None:
        try:
            started = self.network.connect(self.server_var.get(), self.room_var.get())
        except ValueError as exc:
            self.message_var.set(str(exc))
            return
        if not started:
            self.message_var.set("A connection is already active.")
            return
        self.state = AppState()
        self._restart_pending = False
        self._draw_board()
        self._render_status()
        self.message_var.set("Connecting...")
        self.connect_button.configure(state="disabled")
        self.server_entry.configure(state="disabled")
        self.room_entry.configure(state="disabled")

    def _request_restart(self) -> None:
        if not self.state.connected or self.state.game_status != "GAME_OVER" or self._restart_pending:
            return
        self.network.request_restart()
        self._restart_pending = True
        self.message_var.set("Restart requested. Waiting for server...")
        self._render_status()

    def _on_board_click(self, event: tk.Event[tk.Misc]) -> None:
        coordinate = self._geometry().pixel_to_board(event.x, event.y)
        if coordinate is None:
            return
        x, y = coordinate
        if not self.state.can_move(x, y):
            if not self.state.connected:
                self.message_var.set("Not connected.")
            elif self.state.game_status != "PLAYING":
                self.message_var.set("The game is not accepting moves.")
            elif self.state.current_turn != self.state.my_color:
                self.message_var.set("It is not your turn.")
            elif self.state.board[y][x] is not None:
                self.message_var.set("That position is already occupied.")
            return
        self.network.send_move(x, y)
        self.message_var.set(f"Move ({x}, {y}) sent. Waiting for server...")

    def _on_canvas_configure(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(RESIZE_DEBOUNCE_MS, self._finish_resize)

    def _finish_resize(self) -> None:
        self._resize_after_id = None
        if not self._closing:
            self._draw_board()

    def _poll_network_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                self._handle_network_event(event)
        except Empty:
            pass
        if not self._closing:
            self.root.after(50, self._poll_network_events)

    def _handle_network_event(self, event: NetworkEvent) -> None:
        if event.kind == "connected":
            self.state.connected = True
            self.message_var.set(event.message)
        elif event.kind == "disconnected":
            self.state.connected = False
            self._restart_pending = False
            self.connect_button.configure(state="normal")
            self.server_entry.configure(state="normal")
            self.room_entry.configure(state="normal")
            if not self._closing and not self.message_var.get().startswith("Connection lost"):
                self.message_var.set(event.message)
        elif event.kind in {"network_error", "protocol_error"}:
            self.message_var.set(event.message)
        elif event.kind == "connecting":
            self.message_var.set("Connecting...")
        elif event.kind == "message" and event.payload is not None:
            try:
                change = self.state.apply_server_message(event.payload)
            except ValueError as exc:
                LOGGER.warning("Rejected server message: %s", exc)
                self.message_var.set(f"Invalid server message: {exc}")
            else:
                self.message_var.set(change.message)
                if event.payload.get("type") in {"restart", "error"}:
                    self._restart_pending = False
                if change.redraw_board:
                    self._draw_board()
                if not change.handled:
                    LOGGER.warning(change.message)
        self._render_status()

    def _render_status(self) -> None:
        self.you_var.set(self.state.my_color or "-")
        self.turn_var.set(self.state.current_turn or "-")
        self.status_var.set(self.state.game_status.replace("_", " ").title())
        self.settings_var.set(
            f"Board: {self.state.board_size} x {self.state.board_size} / Win: {self.state.win_length}"
        )
        restart_enabled = (
            self.state.connected and self.state.game_status == "GAME_OVER" and not self._restart_pending
        )
        self.restart_button.configure(state="normal" if restart_enabled else "disabled")

    def _geometry(self) -> BoardGeometry:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1:
            width = INITIAL_CANVAS_SIZE
        if height <= 1:
            height = INITIAL_CANVAS_SIZE
        return BoardGeometry.calculate(self.state.board_size, width, height)

    def _draw_board(self) -> None:
        geometry = self._geometry()
        self.canvas.delete("all")
        self._draw_grid(geometry)
        self._draw_stones(geometry)

    def _draw_grid(self, geometry: BoardGeometry) -> None:
        for index in range(self.state.board_size):
            x, y = geometry.board_to_pixel(index, index)
            self.canvas.create_line(
                geometry.origin_x, y, geometry.end_x, y, fill="#3E2B18"
            )
            self.canvas.create_line(
                x, geometry.origin_y, x, geometry.end_y, fill="#3E2B18"
            )
        center = self.state.board_size // 2
        inset = max(2, self.state.board_size // 5)
        far = self.state.board_size - 1 - inset
        star_points = {(center, center)}
        if inset < far:
            star_points.update({(inset, inset), (far, inset), (inset, far), (far, far)})
        star_radius = max(2.0, min(4.0, geometry.spacing * 0.09))
        for x, y in star_points:
            cx, cy = geometry.board_to_pixel(x, y)
            self.canvas.create_oval(
                cx - star_radius,
                cy - star_radius,
                cx + star_radius,
                cy + star_radius,
                fill="#3E2B18",
                outline="",
            )

    def _draw_stones(self, geometry: BoardGeometry) -> None:
        for y, row in enumerate(self.state.board):
            for x, color in enumerate(row):
                if color is not None:
                    self._draw_stone(geometry, x, y, color)
        if self.state.last_move is not None:
            x, y = self.state.last_move
            cx, cy = geometry.board_to_pixel(x, y)
            marker_radius = max(3.0, geometry.stone_radius * 0.32)
            self.canvas.create_rectangle(
                cx - marker_radius,
                cy - marker_radius,
                cx + marker_radius,
                cy + marker_radius,
                outline="#E53935",
                width=2,
            )

    def _draw_stone(self, geometry: BoardGeometry, x: int, y: int, color: str) -> None:
        cx, cy = geometry.board_to_pixel(x, y)
        radius = geometry.stone_radius
        fill = "#171717" if color == BLACK else "#F4F4F4"
        outline = "#000000" if color in (BLACK, WHITE) else "#555555"
        self.canvas.create_oval(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            fill=fill,
            outline=outline,
            width=1,
        )

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
            self._resize_after_id = None
        self.network.shutdown()
        self.root.destroy()
