from __future__ import annotations

import logging
from pathlib import Path
from queue import Empty, Queue
import tkinter as tk
from tkinter import ttk

from .board import BoardGeometry
from .board_renderer import OthelloBoardGeometry
from .client_settings import (
    ClientSettings,
    default_settings_path,
    load_client_settings,
    normalize_server_url,
    save_client_settings,
)
from .game_type import GameType
from .network import NetworkClient, NetworkEvent
from .room_name import MAX_ROOM_NAME_LENGTH, normalize_room_name
from .state import AppState, BLACK, DISCONNECTED, IN_ROOM, LOBBY, RoomSummary, WHITE
from .stone_image import create_stone_photo

LOGGER = logging.getLogger(__name__)
INITIAL_CANVAS_SIZE = 780
RESIZE_DEBOUNCE_MS = 40
FORBIDDEN_COLOR = "#C62828"
FORBIDDEN_REJECTED_COLOR = "#FF5252"
FORBIDDEN_FLASH_MS = 900


class OmokApp:
    def __init__(self, root: tk.Tk, settings_path: Path | None = None) -> None:
        self.root = root
        self.root.title("Online Gomoku & Othello")
        self.root.geometry("900x950")
        self.root.minsize(760, 720)
        self.state = AppState()
        self.events: Queue[NetworkEvent] = Queue()
        self.network = NetworkClient(self.events)
        self._connecting = False
        self._room_request_pending = False
        self._leave_pending = False
        self._restart_pending = False
        self._move_pending = False
        self._closing = False
        self._resize_after_id: str | None = None
        self._forbidden_flash_after_id: str | None = None
        self.hover_position: tuple[int, int] | None = None
        self._preview_item_id: int | None = None
        self._selected_room_id: str | None = None
        self.room_cards: dict[str, tk.Button] = {}
        self._room_grid_column_count = 0
        self._create_room_modal_open = False
        self._settings_modal_open = False
        self._settings_path = settings_path or default_settings_path()
        client_settings = load_client_settings(self._settings_path)

        self.server_var = tk.StringVar(value=client_settings.server_url)
        self.room_var = tk.StringVar(value="-")
        self.you_var = tk.StringVar(value="-")
        self.turn_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="Disconnected")
        self.settings_var = tk.StringVar(value="Board: 15 x 15 / Win: 5")
        self.game_type_var = tk.StringVar(value="-")
        self.score_var = tk.StringVar(value="")
        self.message_var = tk.StringVar(value="Connect to the server.")
        self._create_room_name_var = tk.StringVar()
        self._create_room_error_var = tk.StringVar()
        self._create_room_game_type_var = tk.StringVar(value=GameType.GOMOKU.value)
        self._settings_server_var = tk.StringVar(value=client_settings.server_url)
        self._settings_error_var = tk.StringVar()
        self._stone_images = {
            None: create_stone_photo(self.root, None),
            BLACK: create_stone_photo(self.root, BLACK),
            WHITE: create_stone_photo(self.root, WHITE),
        }

        self._build_ui()
        self._render_status()
        self._render_view()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(50, self._poll_network_events)

    def _build_ui(self) -> None:
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer = ttk.Frame(self.root, padding=10)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        self.content_frame = ttk.Frame(outer)
        self.content_frame.grid(row=0, column=0, sticky="nsew")
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.columnconfigure(0, weight=1)

        self._build_connection_frame()
        self._build_lobby_frame()
        self._build_game_frame()

        footer = ttk.Frame(outer, padding=(0, 7, 0, 0))
        footer.grid(row=1, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.message_var).grid(row=0, column=0, sticky="w")
        footer.columnconfigure(0, weight=1)

    def _build_connection_frame(self) -> None:
        self.connection_frame = ttk.Frame(self.content_frame, padding=30)
        self.connection_frame.rowconfigure(0, weight=1)
        self.connection_frame.rowconfigure(2, weight=1)
        self.connection_frame.columnconfigure(0, weight=1)

        self.connect_button = ttk.Button(
            self.connection_frame,
            text="Connect",
            command=self._connect,
            padding=(42, 16),
        )
        self.connect_button.grid(row=1, column=0)
        self.settings_button = tk.Button(
            self.connection_frame,
            text="⚙",
            command=self._open_settings_modal,
            font=("Segoe UI Symbol", 22),
            foreground="#4B4033",
            background="#F4E8D0",
            activebackground="#E8D3AE",
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=6,
            cursor="hand2",
            takefocus=True,
        )
        self.settings_button.grid(row=3, column=0, sticky="se")

        self.settings_modal_canvas = tk.Canvas(
            self.connection_frame,
            background="#6B6258",
            highlightthickness=0,
            takefocus=True,
        )
        self.settings_modal_canvas.bind(
            "<Configure>", lambda _event: self._draw_settings_modal()
        )
        self.settings_server_entry = ttk.Entry(
            self.settings_modal_canvas,
            textvariable=self._settings_server_var,
            width=42,
        )
        self.settings_modal_error_label = tk.Label(
            self.settings_modal_canvas,
            textvariable=self._settings_error_var,
            foreground="#B42318",
            background="#FFF8EA",
            anchor="w",
        )
        self.settings_modal_cancel_button = ttk.Button(
            self.settings_modal_canvas,
            text="Cancel",
            command=self._close_settings_modal,
        )
        self.settings_modal_save_button = ttk.Button(
            self.settings_modal_canvas,
            text="Save",
            command=self._save_settings,
        )
        for widget in (
            self.settings_server_entry,
            self.settings_modal_cancel_button,
            self.settings_modal_save_button,
        ):
            widget.bind("<Escape>", lambda _event: self._close_settings_modal())
        self.settings_server_entry.bind(
            "<Return>", lambda _event: self._save_settings()
        )

    def _build_lobby_frame(self) -> None:
        self.lobby_frame = ttk.LabelFrame(self.content_frame, text="Lobby", padding=10)
        self.lobby_frame.rowconfigure(1, weight=1)
        self.lobby_frame.columnconfigure(0, weight=1)

        lobby_header = ttk.Frame(self.lobby_frame, padding=(0, 0, 0, 10))
        lobby_header.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(lobby_header, text="Connected Server:").pack(side="left")
        ttk.Label(lobby_header, textvariable=self.server_var).pack(side="left", padx=(5, 0))
        self.lobby_disconnect_button = ttk.Button(
            lobby_header, text="Disconnect", command=self._disconnect
        )
        self.lobby_disconnect_button.pack(side="right")

        self.room_canvas = tk.Canvas(
            self.lobby_frame,
            background="#F4E8D0",
            highlightthickness=1,
            highlightbackground="#C9A875",
        )
        self.room_canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            self.lobby_frame, orient="vertical", command=self.room_canvas.yview
        )
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.room_canvas.configure(yscrollcommand=scrollbar.set)
        self.room_grid = tk.Frame(self.room_canvas, background="#F4E8D0")
        self._room_grid_window = self.room_canvas.create_window(
            0, 0, anchor="nw", window=self.room_grid
        )
        self.room_grid.bind(
            "<Configure>",
            lambda _event: self.room_canvas.configure(
                scrollregion=self.room_canvas.bbox("all")
            ),
        )
        self.room_canvas.bind("<Configure>", self._on_room_canvas_configure)

        self.lobby_empty_label = ttk.Label(
            self.lobby_frame,
            text="현재 생성된 방이 없습니다. 새 방을 만들어 주세요.",
            anchor="center",
        )
        self.lobby_empty_label.grid(row=2, column=0, columnspan=2, pady=(8, 0), sticky="ew")

        controls = ttk.Frame(self.lobby_frame, padding=(0, 10, 0, 0))
        controls.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.create_room_button = ttk.Button(
            controls, text="Create Room", command=self._create_room
        )
        self.create_room_button.pack(side="left")
        self.join_room_button = ttk.Button(
            controls, text="Join Room", command=self._join_selected_room
        )
        self.join_room_button.pack(side="left", padx=7)
        self.refresh_rooms_button = ttk.Button(
            controls, text="Refresh", command=self._request_room_list
        )
        self.refresh_rooms_button.pack(side="left")

        self.create_room_modal_canvas = tk.Canvas(
            self.lobby_frame,
            background="#6B6258",
            highlightthickness=0,
            takefocus=True,
        )
        self.create_room_modal_canvas.bind(
            "<Configure>", lambda _event: self._draw_create_room_modal()
        )
        self.create_room_name_entry = ttk.Entry(
            self.create_room_modal_canvas,
            textvariable=self._create_room_name_var,
            width=36,
        )
        self.create_room_modal_error_label = tk.Label(
            self.create_room_modal_canvas,
            textvariable=self._create_room_error_var,
            foreground="#B42318",
            background="#FFF8EA",
            anchor="w",
        )
        self.create_gomoku_radio = ttk.Radiobutton(
            self.create_room_modal_canvas,
            text="Gomoku",
            variable=self._create_room_game_type_var,
            value=GameType.GOMOKU.value,
        )
        self.create_othello_radio = ttk.Radiobutton(
            self.create_room_modal_canvas,
            text="Othello",
            variable=self._create_room_game_type_var,
            value=GameType.OTHELLO.value,
        )
        self.create_room_modal_cancel_button = ttk.Button(
            self.create_room_modal_canvas,
            text="Cancel",
            command=self._close_create_room_modal,
        )
        self.create_room_modal_submit_button = ttk.Button(
            self.create_room_modal_canvas,
            text="Create",
            command=self._submit_create_room,
        )
        for widget in (
            self.create_room_name_entry,
            self.create_gomoku_radio,
            self.create_othello_radio,
            self.create_room_modal_cancel_button,
            self.create_room_modal_submit_button,
        ):
            widget.bind("<Escape>", lambda _event: self._close_create_room_modal())
        self.create_room_name_entry.bind(
            "<Return>", lambda _event: self._submit_create_room()
        )

    def _build_game_frame(self) -> None:
        self.game_frame = ttk.Frame(self.content_frame)
        self.game_frame.rowconfigure(1, weight=1)
        self.game_frame.columnconfigure(0, weight=1)

        info = ttk.LabelFrame(self.game_frame, text="Game", padding=7)
        info.grid(row=0, column=0, sticky="ew")
        ttk.Label(info, text="Room:").grid(row=0, column=0)
        ttk.Label(
            info,
            textvariable=self.room_var,
            font=("TkDefaultFont", 11, "bold"),
        ).grid(
            row=0, column=1, columnspan=5, padx=(4, 0), pady=(0, 6), sticky="w"
        )
        ttk.Label(info, text="Game:").grid(row=0, column=7, sticky="e")
        ttk.Label(info, textvariable=self.game_type_var, width=9).grid(
            row=0, column=8, columnspan=2, padx=(4, 0), sticky="w"
        )
        ttk.Label(info, text="You:").grid(row=1, column=0)
        self.you_stone_label = ttk.Label(info, image=self._stone_images[None])
        self.you_stone_label.grid(row=1, column=1, padx=(4, 12), sticky="w")
        ttk.Label(info, text="Turn:").grid(row=1, column=2)
        self.turn_stone_label = ttk.Label(info, image=self._stone_images[None])
        self.turn_stone_label.grid(row=1, column=3, padx=(4, 12), sticky="w")
        ttk.Label(info, text="Status:").grid(row=1, column=4)
        ttk.Label(info, textvariable=self.status_var, width=11).grid(
            row=1, column=5, sticky="w"
        )
        ttk.Label(info, textvariable=self.settings_var).grid(
            row=1, column=6, padx=(10, 0), sticky="e"
        )
        info.columnconfigure(6, weight=1)
        ttk.Label(info, textvariable=self.score_var).grid(
            row=2, column=0, columnspan=7, pady=(5, 0), sticky="w"
        )
        self.restart_button = ttk.Button(info, text="Restart", command=self._request_restart)
        self.restart_button.grid(row=1, column=7, padx=(10, 0))
        self.leave_room_button = ttk.Button(info, text="Leave Room", command=self._leave_room)
        self.leave_room_button.grid(row=1, column=8, padx=(7, 0))
        self.game_disconnect_button = ttk.Button(
            info, text="Disconnect", command=self._disconnect
        )
        self.game_disconnect_button.grid(row=1, column=9, padx=(7, 0))

        self.canvas = tk.Canvas(
            self.game_frame,
            width=INITIAL_CANVAS_SIZE,
            height=INITIAL_CANVAS_SIZE,
            background="#D9A85C",
            highlightthickness=1,
            highlightbackground="#7B542B",
        )
        self.canvas.grid(row=1, column=0, pady=(7, 0), sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_board_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _open_settings_modal(self) -> None:
        if self.state.connected or self._connecting or self._settings_modal_open:
            return
        self._settings_modal_open = True
        self._settings_server_var.set(self.server_var.get())
        self._settings_error_var.set("")
        self.settings_modal_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.settings_modal_canvas.tk.call("raise", self.settings_modal_canvas._w)
        self.root.update_idletasks()
        self._draw_settings_modal()
        self.settings_server_entry.focus_set()
        self._render_controls()

    def _draw_settings_modal(self) -> None:
        if not self._settings_modal_open:
            return
        canvas = self.settings_modal_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 560)
        height = max(canvas.winfo_height(), 360)
        center_x = width / 2
        center_y = height / 2
        panel_width = min(540, width - 50)
        panel_height = 270
        left = center_x - panel_width / 2
        right = center_x + panel_width / 2
        top = center_y - panel_height / 2
        bottom = center_y + panel_height / 2

        canvas.create_rectangle(0, 0, width, height, fill="#6B6258", outline="")
        canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill="#FFF8EA",
            outline="#7B542B",
            width=3,
        )
        canvas.create_text(
            center_x,
            top + 44,
            text="Connection Settings",
            fill="#3E2B18",
            font=("TkDefaultFont", 18, "bold"),
        )
        canvas.create_text(
            left + 32,
            top + 91,
            text="Server URL",
            anchor="w",
            fill="#3E2B18",
            font=("TkDefaultFont", 10, "bold"),
        )
        canvas.create_window(
            center_x,
            top + 124,
            window=self.settings_server_entry,
            width=panel_width - 64,
        )
        canvas.create_window(
            center_x,
            top + 160,
            window=self.settings_modal_error_label,
            width=panel_width - 64,
        )
        canvas.create_window(
            center_x - 48,
            bottom - 42,
            window=self.settings_modal_cancel_button,
        )
        canvas.create_window(
            center_x + 48,
            bottom - 42,
            window=self.settings_modal_save_button,
        )

    def _save_settings(self) -> None:
        if not self._settings_modal_open:
            return
        try:
            server_url = normalize_server_url(self._settings_server_var.get())
            save_client_settings(
                ClientSettings(server_url=server_url), self._settings_path
            )
        except (OSError, ValueError) as exc:
            self._settings_error_var.set(str(exc))
            return
        self.server_var.set(server_url)
        self._close_settings_modal()
        self.message_var.set("Connection settings saved.")

    def _close_settings_modal(self) -> None:
        if not self._settings_modal_open:
            return
        self._settings_modal_open = False
        self.settings_modal_canvas.place_forget()
        self.settings_modal_canvas.delete("all")
        self._settings_server_var.set(self.server_var.get())
        self._settings_error_var.set("")
        self._render_controls()

    def _disconnect(self) -> None:
        if not self.state.connected:
            return
        self.network.disconnect()
        self.lobby_disconnect_button.configure(state="disabled")
        self.game_disconnect_button.configure(state="disabled")
        self.message_var.set("Disconnecting...")

    def _connect(self) -> None:
        if self._settings_modal_open:
            return
        try:
            started = self.network.connect(self.server_var.get())
        except ValueError as exc:
            self.message_var.set(str(exc))
            return
        if not started:
            self.message_var.set("A connection is already active.")
            return
        self._connecting = True
        self._clear_hover()
        self.state = AppState()
        self._clear_pending_requests()
        self.message_var.set("Connecting...")
        self._render_status()
        self._render_view()

    def _request_room_list(self) -> None:
        if self.state.connected and self.state.view_state == LOBBY:
            self.network.request_room_list()

    def _create_room(self) -> None:
        if (
            self.state.view_state != LOBBY
            or self._room_request_pending
            or self._create_room_modal_open
        ):
            return
        self._create_room_modal_open = True
        self._create_room_name_var.set("")
        self._create_room_error_var.set("")
        self._create_room_game_type_var.set(GameType.GOMOKU.value)
        othello_supported = GameType.OTHELLO in self.state.supported_game_types
        self.create_othello_radio.configure(
            state="normal" if othello_supported else "disabled"
        )
        self.create_room_modal_canvas.place(
            x=0, y=0, relwidth=1, relheight=1
        )
        self.create_room_modal_canvas.tk.call(
            "raise", self.create_room_modal_canvas._w
        )
        self.root.update_idletasks()
        self._draw_create_room_modal()
        self.create_room_name_entry.focus_set()
        self._render_controls()

    def _draw_create_room_modal(self) -> None:
        if not self._create_room_modal_open:
            return
        canvas = self.create_room_modal_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 360)
        center_x = width / 2
        center_y = height / 2
        panel_width = min(460, width - 50)
        panel_height = 340
        left = center_x - panel_width / 2
        right = center_x + panel_width / 2
        top = center_y - panel_height / 2
        bottom = center_y + panel_height / 2

        canvas.create_rectangle(
            0, 0, width, height, fill="#6B6258", outline="", tags=("modal",)
        )
        canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill="#FFF8EA",
            outline="#7B542B",
            width=3,
            tags=("modal",),
        )
        canvas.create_text(
            center_x,
            top + 42,
            text="Create Room",
            fill="#3E2B18",
            font=("TkDefaultFont", 18, "bold"),
            tags=("modal",),
        )
        canvas.create_text(
            left + 30,
            top + 82,
            text=f"방 이름 (최대 {MAX_ROOM_NAME_LENGTH}자)",
            anchor="w",
            fill="#3E2B18",
            font=("TkDefaultFont", 10, "bold"),
            tags=("modal",),
        )
        canvas.create_window(
            center_x,
            top + 115,
            window=self.create_room_name_entry,
            width=panel_width - 60,
            tags=("modal",),
        )
        canvas.create_window(
            center_x,
            top + 150,
            window=self.create_room_modal_error_label,
            width=panel_width - 60,
            tags=("modal",),
        )
        canvas.create_text(
            left + 30,
            top + 190,
            text="Game",
            anchor="w",
            fill="#3E2B18",
            font=("TkDefaultFont", 10, "bold"),
            tags=("modal",),
        )
        canvas.create_window(
            left + 105,
            top + 220,
            window=self.create_gomoku_radio,
            anchor="w",
            tags=("modal",),
        )
        canvas.create_window(
            left + 220,
            top + 220,
            window=self.create_othello_radio,
            anchor="w",
            tags=("modal",),
        )
        canvas.create_window(
            center_x - 48,
            bottom - 42,
            window=self.create_room_modal_cancel_button,
            tags=("modal",),
        )
        canvas.create_window(
            center_x + 48,
            bottom - 42,
            window=self.create_room_modal_submit_button,
            tags=("modal",),
        )

    def _submit_create_room(self) -> None:
        if not self._create_room_modal_open:
            return
        try:
            room_name = normalize_room_name(self._create_room_name_var.get())
            game_type = GameType.from_wire(self._create_room_game_type_var.get())
            if game_type not in self.state.supported_game_types:
                raise ValueError("서버가 지원하지 않는 게임 종류입니다.")
        except ValueError as exc:
            self._create_room_error_var.set(str(exc))
            return
        self._room_request_pending = True
        self.network.create_room(room_name, game_type)
        self._close_create_room_modal()
        self.message_var.set(f"Creating {game_type.label} room '{room_name}'...")
        self._render_controls()

    def _close_create_room_modal(self) -> None:
        if not self._create_room_modal_open:
            return
        self._create_room_modal_open = False
        self.create_room_modal_canvas.place_forget()
        self.create_room_modal_canvas.delete("all")
        self._create_room_name_var.set("")
        self._create_room_error_var.set("")
        self._create_room_game_type_var.set(GameType.GOMOKU.value)
        self._render_controls()

    def _join_selected_room(self) -> None:
        room = self._selected_room()
        if (
            self.state.view_state != LOBBY
            or self._room_request_pending
            or room is None
            or not room.can_join
        ):
            return
        self._room_request_pending = True
        self.network.join_room(room.room_id)
        self.message_var.set(f"Joining '{room.room_name}'...")
        self._render_controls()

    def _leave_room(self) -> None:
        if self.state.view_state != IN_ROOM or self._leave_pending:
            return
        self._leave_pending = True
        self.network.leave_room()
        self.message_var.set("Leaving room... Waiting for server confirmation.")
        self._render_controls()

    def _request_restart(self) -> None:
        if (
            self.state.view_state != IN_ROOM
            or not self.state.connected
            or not self.state.is_finished
            or self._restart_pending
        ):
            return
        self.network.request_restart()
        self._restart_pending = True
        self.message_var.set("Restart requested. Waiting for opponent...")
        self._render_controls()

    def _selected_room(self) -> RoomSummary | None:
        return next(
            (room for room in self.state.rooms if room.room_id == self._selected_room_id),
            None,
        )

    def _select_room(self, room_id: str) -> None:
        if room_id not in self.room_cards:
            return
        self._selected_room_id = room_id
        self._render_room_card_selection()
        self._render_controls()

    def _on_room_double_click(self, room_id: str) -> None:
        self._select_room(room_id)
        self._join_selected_room()

    def _on_room_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        self.room_canvas.itemconfigure(self._room_grid_window, width=event.width)
        self._layout_room_cards(event.width)

    def _on_board_click(self, event: tk.Event[tk.Misc]) -> None:
        if self._move_pending:
            return
        coordinate = self._pointer_to_board(event.x, event.y)
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
            elif self.state.is_forbidden_for_me(x, y):
                label = self.state.forbidden_label_at(x, y) or "금수"
                self.message_var.set(f"{label} 자리입니다. 다른 곳에 두세요.")
            elif self.state.board[y][x] is not None:
                self.message_var.set("That position is already occupied.")
            return
        self.network.send_move(x, y)
        self._move_pending = True
        self._clear_hover()
        self.message_var.set(f"Move ({x}, {y}) sent. Waiting for server...")

    def _on_mouse_move(self, event: tk.Event[tk.Misc]) -> None:
        coordinate = self._pointer_to_board(event.x, event.y)
        if coordinate is not None and (
            self._move_pending or not self.state.can_move(*coordinate)
        ):
            coordinate = None
        self._set_hover_position(coordinate)

    def _on_mouse_leave(self, _event: tk.Event[tk.Misc]) -> None:
        self._clear_hover()

    def _pointer_to_board(self, pixel_x: float, pixel_y: float) -> tuple[int, int] | None:
        return self._geometry().pixel_to_board(pixel_x, pixel_y)

    def _set_hover_position(self, coordinate: tuple[int, int] | None) -> None:
        if coordinate == self.hover_position:
            return
        self.hover_position = coordinate
        self._render_preview(self._geometry())

    def _clear_hover(self) -> None:
        self.hover_position = None
        if self._preview_item_id is not None:
            self.canvas.delete(self._preview_item_id)
            self._preview_item_id = None

    def _clear_pending_requests(self) -> None:
        self._room_request_pending = False
        self._leave_pending = False
        self._restart_pending = False
        self._move_pending = False
        self._cancel_forbidden_flash()

    def _sync_forbidden_flash(self) -> None:
        """Let a rejected point fade on its own instead of sticking."""
        self._cancel_forbidden_flash()
        if self.state.rejected_point is None:
            return
        self._forbidden_flash_after_id = self.root.after(
            FORBIDDEN_FLASH_MS, self._clear_rejected_point
        )

    def _cancel_forbidden_flash(self) -> None:
        if self._forbidden_flash_after_id is not None:
            self.root.after_cancel(self._forbidden_flash_after_id)
            self._forbidden_flash_after_id = None

    def _clear_rejected_point(self) -> None:
        self._forbidden_flash_after_id = None
        if self.state.rejected_point is None:
            return
        self.state.rejected_point = None
        if self.state.view_state == IN_ROOM:
            self._draw_board()

    def _on_canvas_configure(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(RESIZE_DEBOUNCE_MS, self._finish_resize)

    def _finish_resize(self) -> None:
        self._resize_after_id = None
        if not self._closing and self.state.view_state == IN_ROOM:
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
            self._connecting = False
            self.state.connected = True
            self.message_var.set("Connected. Waiting for lobby confirmation...")
        elif event.kind == "disconnected":
            self._connecting = False
            self._clear_hover()
            self.state.reset_connection()
            self._clear_pending_requests()
            if not self._closing and not self.message_var.get().startswith("Connection lost"):
                self.message_var.set(event.message)
        elif event.kind in {"network_error", "protocol_error"}:
            self.message_var.set(event.message)
        elif event.kind == "connecting":
            self._connecting = True
            self.message_var.set("Connecting...")
        elif event.kind == "message" and event.payload is not None:
            self._handle_server_message(event.payload)
        self._render_status()
        self._render_view()

    def _handle_server_message(self, payload: dict[str, object]) -> None:
        message_type = payload.get("type")
        if message_type in {
            "joined",
            "left_room",
            "game_start",
            "move_result",
            "game_over",
            "game_state",
            "player_disconnected",
            "restart",
        }:
            self._clear_hover()
        try:
            change = self.state.apply_server_message(payload)
        except ValueError as exc:
            LOGGER.warning("Rejected server message: %s", exc)
            self.message_var.set(f"Invalid server message: {exc}")
            return

        self.message_var.set(change.message)
        if message_type == "connected":
            self.network.request_room_list()
        elif message_type == "room_list":
            self._render_room_list()
        elif message_type == "joined":
            self._room_request_pending = False
            self._leave_pending = False
            self._restart_pending = False
            self._move_pending = False
        elif message_type == "left_room":
            self._leave_pending = False
            self._restart_pending = False
            self._move_pending = False
            self.network.request_room_list()
        elif message_type == "error":
            self._clear_pending_requests()
            self._sync_forbidden_flash()
        elif message_type in {"move_result", "game_state", "game_over"}:
            self._move_pending = False
        elif message_type == "restart":
            self._restart_pending = False
            self._move_pending = False
        if change.redraw_board and self.state.view_state == IN_ROOM:
            self._draw_board()
        if not change.handled:
            LOGGER.warning(change.message)

    def _render_view(self) -> None:
        for frame in (self.connection_frame, self.lobby_frame, self.game_frame):
            frame.grid_remove()
        if self.state.view_state != IN_ROOM:
            self._draw_board()
        if self.state.view_state == LOBBY:
            self.lobby_frame.grid(row=0, column=0, sticky="nsew")
            self._render_room_list()
        elif self.state.view_state == IN_ROOM:
            self.game_frame.grid(row=0, column=0, sticky="nsew")
            self._draw_board()
        else:
            self.connection_frame.grid(row=0, column=0, sticky="nsew")
        if self.state.view_state != LOBBY:
            self._close_create_room_modal()
        if self.state.view_state != DISCONNECTED:
            self._close_settings_modal()
        self._render_controls()

    def _render_room_list(self) -> None:
        if self._selected_room_id not in {room.room_id for room in self.state.rooms}:
            self._selected_room_id = None
        for card in self.room_cards.values():
            card.destroy()
        self.room_cards.clear()
        for room in self.state.rooms:
            card = tk.Button(
                self.room_grid,
                text=(
                    f"{room.room_name}\n"
                    f"{room.game_type.label} · {room.board_size} × {room.board_size}\n"
                    f"{room.players} / {room.max_players} · {room.status}"
                ),
                image=self._stone_images[BLACK],
                compound="top",
                command=lambda room_id=room.room_id: self._select_room(room_id),
                background="#FFF8EA",
                activebackground="#F7DDAF",
                foreground="#3E2B18",
                font=("TkDefaultFont", 10, "bold"),
                relief="raised",
                borderwidth=2,
                padx=18,
                pady=12,
                cursor="hand2",
            )
            card.bind(
                "<Double-1>",
                lambda _event, room_id=room.room_id: self._on_room_double_click(room_id),
            )
            self.room_cards[room.room_id] = card
        self._layout_room_cards(self.room_canvas.winfo_width())
        self._render_room_card_selection()
        if self.state.rooms:
            self.lobby_empty_label.grid_remove()
        else:
            self.lobby_empty_label.grid()
        self._render_controls()

    def _layout_room_cards(self, available_width: int) -> None:
        columns = max(1, available_width // 220) if available_width > 1 else 3
        for column in range(self._room_grid_column_count):
            self.room_grid.columnconfigure(column, weight=0, uniform="")
        for column in range(columns):
            self.room_grid.columnconfigure(column, weight=1, uniform="room_card")
        self._room_grid_column_count = columns
        for index, card in enumerate(self.room_cards.values()):
            card.grid(
                row=index // columns,
                column=index % columns,
                padx=10,
                pady=10,
                sticky="nsew",
            )

    def _render_room_card_selection(self) -> None:
        for room_id, card in self.room_cards.items():
            selected = room_id == self._selected_room_id
            card.configure(
                background="#F4C873" if selected else "#FFF8EA",
                relief="sunken" if selected else "raised",
                borderwidth=3 if selected else 2,
                state="disabled" if self._create_room_modal_open else "normal",
            )

    def _render_status(self) -> None:
        self.room_var.set(self.state.room_name or self.state.room_id or "-")
        self.game_type_var.set(self.state.game_type.label if self.state.game_type else "-")
        self.you_var.set(self.state.my_color or "-")
        self.turn_var.set(self.state.current_turn or "-")
        self.you_stone_label.configure(
            image=self._stone_images.get(self.state.my_color, self._stone_images[None])
        )
        self.turn_stone_label.configure(
            image=self._stone_images.get(self.state.current_turn, self._stone_images[None])
        )
        self.status_var.set(self.state.game_status.replace("_", " ").title())
        if self.state.game_type is GameType.OTHELLO:
            self.settings_var.set(f"Board: {self.state.board_size} x {self.state.board_size}")
            self.score_var.set(
                f"Score: Black {self.state.score[BLACK]} · White {self.state.score[WHITE]}"
            )
        else:
            self.settings_var.set(
                f"Board: {self.state.board_size} x {self.state.board_size} / "
                f"Win: {self.state.win_length}"
            )
            self.score_var.set("")
        self._render_controls()

    def _render_controls(self) -> None:
        connection_available = (
            not self.state.connected
            and not self._connecting
            and not self._settings_modal_open
        )
        self.connect_button.configure(
            text="Connect",
            state="normal" if connection_available else "disabled",
        )
        self.settings_button.configure(
            state="normal" if connection_available else "disabled"
        )
        in_lobby = self.state.connected and self.state.view_state == LOBBY
        lobby_available = in_lobby and not self._create_room_modal_open
        self.create_room_button.configure(
            state="normal"
            if lobby_available and not self._room_request_pending
            else "disabled"
        )
        room = self._selected_room()
        can_join = (
            lobby_available
            and not self._room_request_pending
            and room is not None
            and room.can_join
        )
        self.join_room_button.configure(state="normal" if can_join else "disabled")
        self.refresh_rooms_button.configure(state="normal" if lobby_available else "disabled")
        disconnect_state = "normal" if self.state.connected else "disabled"
        self.lobby_disconnect_button.configure(
            state=disconnect_state if not self._create_room_modal_open else "disabled"
        )
        self.game_disconnect_button.configure(state=disconnect_state)
        for card in self.room_cards.values():
            card.configure(state="disabled" if self._create_room_modal_open else "normal")
        self.leave_room_button.configure(
            state="normal"
            if self.state.view_state == IN_ROOM and not self._leave_pending
            else "disabled"
        )
        self.restart_button.configure(
            state="normal"
            if self.state.view_state == IN_ROOM
            and self.state.connected
            and self.state.is_finished
            and not self._restart_pending
            else "disabled"
        )

    def _geometry(self) -> BoardGeometry | OthelloBoardGeometry:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1:
            width = INITIAL_CANVAS_SIZE
        if height <= 1:
            height = INITIAL_CANVAS_SIZE
        if self.state.game_type is GameType.OTHELLO:
            return OthelloBoardGeometry.calculate(self.state.board_size, width, height)
        return BoardGeometry.calculate(self.state.board_size, width, height)

    def _draw_board(self) -> None:
        geometry = self._geometry()
        self.canvas.delete("all")
        self._preview_item_id = None
        if not self.state.connected or self.state.view_state != IN_ROOM:
            return
        self.canvas.configure(
            background="#2E7D32"
            if self.state.game_type is GameType.OTHELLO
            else "#D9A85C",
            highlightbackground="#17451B"
            if self.state.game_type is GameType.OTHELLO
            else "#7B542B",
        )
        self._draw_grid(geometry)
        self._draw_forbidden_moves(geometry)
        self._draw_legal_moves(geometry)
        self._draw_stones(geometry)
        self._draw_result_overlay(geometry)
        self._render_preview(geometry)

    def _draw_grid(self, geometry: BoardGeometry | OthelloBoardGeometry) -> None:
        if isinstance(geometry, OthelloBoardGeometry):
            self.canvas.create_rectangle(
                geometry.origin_x,
                geometry.origin_y,
                geometry.end_x,
                geometry.end_y,
                fill="#2E7D32",
                outline="#102F13",
                width=2,
            )
            for index in range(geometry.board_size + 1):
                offset = index * geometry.spacing
                self.canvas.create_line(
                    geometry.origin_x,
                    geometry.origin_y + offset,
                    geometry.end_x,
                    geometry.origin_y + offset,
                    fill="#153E18",
                )
                self.canvas.create_line(
                    geometry.origin_x + offset,
                    geometry.origin_y,
                    geometry.origin_x + offset,
                    geometry.end_y,
                    fill="#153E18",
                )
            return
        for index in range(self.state.board_size):
            x, y = geometry.board_to_pixel(index, index)
            self.canvas.create_line(geometry.origin_x, y, geometry.end_x, y, fill="#3E2B18")
            self.canvas.create_line(x, geometry.origin_y, x, geometry.end_y, fill="#3E2B18")
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

    def _draw_forbidden_moves(
        self, geometry: BoardGeometry | OthelloBoardGeometry
    ) -> None:
        """Red crosses on points the server forbids for my own color."""
        if isinstance(geometry, OthelloBoardGeometry):
            return
        if self.state.game_status != "PLAYING":
            return
        if (
            self.state.my_color is None
            or self.state.my_color != self.state.constrained_color
        ):
            return
        arm = max(3.0, geometry.spacing * 0.26)
        width = max(2, int(geometry.spacing * 0.06))
        for x, y in self.state.forbidden_moves:
            cx, cy = geometry.board_to_pixel(x, y)
            for sign in (1, -1):
                self.canvas.create_line(
                    cx - arm,
                    cy - arm * sign,
                    cx + arm,
                    cy + arm * sign,
                    fill=FORBIDDEN_COLOR,
                    width=width,
                    tags=("forbidden_move",),
                )
        self._draw_rejected_point(geometry, arm, width)

    def _draw_rejected_point(
        self,
        geometry: BoardGeometry | OthelloBoardGeometry,
        arm: float,
        width: int,
    ) -> None:
        point = self.state.rejected_point
        if point is None:
            return
        cx, cy = geometry.board_to_pixel(*point)
        self.canvas.create_oval(
            cx - arm,
            cy - arm,
            cx + arm,
            cy + arm,
            outline=FORBIDDEN_REJECTED_COLOR,
            width=width + 1,
            tags=("forbidden_rejected",),
        )

    def _draw_legal_moves(
        self, geometry: BoardGeometry | OthelloBoardGeometry
    ) -> None:
        if not isinstance(geometry, OthelloBoardGeometry):
            return
        if self.state.current_turn != self.state.my_color or self._move_pending:
            return
        marker_radius = max(3.0, geometry.spacing * 0.07)
        for x, y in self.state.legal_moves:
            cx, cy = geometry.board_to_pixel(x, y)
            self.canvas.create_oval(
                cx - marker_radius,
                cy - marker_radius,
                cx + marker_radius,
                cy + marker_radius,
                fill="#B9E3A1",
                outline="",
                tags=("legal_move",),
            )

    def _draw_stones(self, geometry: BoardGeometry | OthelloBoardGeometry) -> None:
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

    def _draw_stone(
        self,
        geometry: BoardGeometry | OthelloBoardGeometry,
        x: int,
        y: int,
        color: str,
    ) -> None:
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

    def _render_preview(self, geometry: BoardGeometry | OthelloBoardGeometry) -> None:
        if self._preview_item_id is not None:
            self.canvas.delete(self._preview_item_id)
            self._preview_item_id = None
        coordinate = self.hover_position
        if coordinate is None or self._move_pending or not self.state.can_move(*coordinate):
            self.hover_position = None
            return
        cx, cy = geometry.board_to_pixel(*coordinate)
        radius = geometry.stone_radius
        outline = "#242424" if self.state.my_color == BLACK else "#FFFFFF"
        self._preview_item_id = self.canvas.create_oval(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            fill="",
            outline=outline,
            width=3,
            dash=(6, 4),
            tags=("preview",),
        )

    def _draw_result_overlay(
        self, geometry: BoardGeometry | OthelloBoardGeometry
    ) -> None:
        if not self.state.is_finished:
            return
        center_x = (geometry.origin_x + geometry.end_x) / 2
        center_y = (geometry.origin_y + geometry.end_y) / 2
        board_pixel_size = geometry.end_x - geometry.origin_x
        panel_width = min(640.0, max(320.0, board_pixel_size * 0.78))
        panel_height = min(190.0, max(120.0, board_pixel_size * 0.22))
        font_size = min(
            44, max(26, int(min(geometry.canvas_width, geometry.canvas_height) * 0.055))
        )
        self.canvas.create_rectangle(
            center_x - panel_width / 2,
            center_y - panel_height / 2,
            center_x + panel_width / 2,
            center_y + panel_height / 2,
            fill="#F8E8C8",
            outline="#7B542B",
            width=3,
            tags=("result_overlay",),
        )
        self.canvas.create_text(
            center_x,
            center_y,
            text=self.state.build_game_over_message(),
            fill="#5A2018",
            font=("TkDefaultFont", font_size, "bold"),
            width=panel_width - 36,
            justify="center",
            tags=("result_overlay",),
        )

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._close_settings_modal()
        self._close_create_room_modal()
        self._clear_hover()
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
            self._resize_after_id = None
        self._cancel_forbidden_flash()
        self.network.shutdown()
        self.root.destroy()
