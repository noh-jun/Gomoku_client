from __future__ import annotations

import logging
from pathlib import Path
from queue import Empty, Queue
import tkinter as tk
from tkinter import ttk

from .board import BoardGeometry
from .board_renderer import OthelloBoardGeometry
from .account import normalize_account_id, validate_password
from .canvas_overlay import (
    ActionModalOverlay,
    CanvasOverlay,
    OverlayAction,
    OverlayOptions,
    SystemBlockingOverlay,
)
from .client_settings import (
    ClientSettings,
    default_settings_path,
    load_client_settings,
    normalize_server_url,
    save_client_settings,
)
from .game_type import GameType
from .network import NetworkClient, NetworkEvent
from .nickname import normalize_nickname
from .chat import normalize_chat_text
from .chat_panel import ChatPanel
from .room_member_list import RoomMemberList
from .room_name import MAX_ROOM_NAME_LENGTH, normalize_room_name
from .state import (
    AppState,
    BLACK,
    DISCONNECTED,
    IN_ROOM,
    LOBBY,
    OBSERVER,
    PLAYER,
    RoomSummary,
    WHITE,
)
from .current_turn_widget import CurrentTurnWidget
from .connection_view import ConnectionView
from .create_account_view import CreateAccountView
from .login_view import LoginView
from .stone_image import create_stone_photo
from .turn_timer import TurnTimer
from .turn_timer_widget import TurnTimerWidget
from .version import CLIENT_VERSION

LOGGER = logging.getLogger(__name__)
INITIAL_CANVAS_SIZE = 780
RESIZE_DEBOUNCE_MS = 40
FORBIDDEN_COLOR = "#C62828"
FORBIDDEN_REJECTED_COLOR = "#FF5252"
FORBIDDEN_FLASH_MS = 900
INFINITE_TURN_TIME = "INFINITE"
TURN_TIME_OPTIONS = ("5", "10", "15", "30", "60", INFINITE_TURN_TIME)


class OmokApp:
    def __init__(self, root: tk.Tk, settings_path: Path | None = None) -> None:
        self.root = root
        self.root.title("Online Gomoku & Othello")
        self.root.geometry("1120x950")
        self.root.minsize(900, 720)
        self.state = AppState()
        self.events: Queue[NetworkEvent] = Queue()
        self.network = NetworkClient(self.events)
        self._connecting = False
        self._account_request_pending = False
        self._login_request_pending = False
        self._room_request_pending = False
        self._leave_pending = False
        self._ready_request_pending = False
        self._role_change_pending = False
        self._move_pending = False
        self._turn_timer_display_expired = False
        self._undo_pending = False
        self._undo_waiting_for_game_state = False
        self._resign_pending = False
        self._result_popup_dismissed = False
        self._closing = False
        self._pending_account_id: str | None = None
        self._pending_account_password: str | None = None
        self._resize_after_id: str | None = None
        self._forbidden_flash_after_id: str | None = None
        self.hover_position: tuple[int, int] | None = None
        self._preview_item_id: int | None = None
        self.room_cards: dict[str, tk.Button] = {}
        self._room_grid_column_count = 0
        self._create_room_modal_open = False
        self._join_room_modal_open = False
        self._join_room_id: str | None = None
        self._join_room_name = ""
        self._settings_modal_open = False
        self._authentication_view = "connection"
        self._settings_path = settings_path or default_settings_path()
        client_settings = load_client_settings(self._settings_path)

        self.server_var = tk.StringVar(value=client_settings.server_url)
        self.message_var = tk.StringVar(value="Log in to continue.")
        self.login_account_id_var = tk.StringVar(value=client_settings.account_id)
        self.login_password_var = tk.StringVar(value=client_settings.password)
        self.auto_login_var = tk.BooleanVar(value=client_settings.auto_login)
        self.create_account_id_var = tk.StringVar()
        self.create_account_password_var = tk.StringVar()
        self.create_account_password_confirm_var = tk.StringVar()
        self.create_account_nickname_var = tk.StringVar()
        self._create_room_name_var = tk.StringVar()
        self._create_room_error_var = tk.StringVar()
        self._create_room_game_type_var = tk.StringVar(value=GameType.GOMOKU.value)
        self._create_room_turn_time_var = tk.StringVar(value=INFINITE_TURN_TIME)
        self._settings_server_var = tk.StringVar(value=client_settings.server_url)
        self._settings_account_id_var = tk.StringVar(value=client_settings.account_id)
        self._settings_auto_login_var = tk.BooleanVar(value=client_settings.auto_login)
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
        self.root.after(0, self._connect_to_server)

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
        self._build_login_frame()
        self._build_create_account_frame()
        self._build_lobby_frame()
        self._build_game_frame()

        footer = ttk.Frame(outer, padding=(0, 7, 0, 0))
        footer.grid(row=1, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.message_var).grid(row=0, column=0, sticky="w")
        footer.columnconfigure(0, weight=1)

    def _build_connection_frame(self) -> None:
        self.connection_frame = ConnectionView(
            self.content_frame,
            server_var=self.server_var,
            on_retry=self._connect_to_server,
            on_settings=self._open_settings_modal,
        )
        self.settings_button = self.connection_frame.settings_button

        self.settings_modal_canvas = tk.Canvas(
            self.content_frame,
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
        self.settings_auto_login_check = ttk.Checkbutton(
            self.settings_modal_canvas,
            text="Auto Login",
            variable=self._settings_auto_login_var,
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

    def _build_login_frame(self) -> None:
        self.login_frame = LoginView(
            self.content_frame,
            account_id_var=self.login_account_id_var,
            password_var=self.login_password_var,
            auto_login_var=self.auto_login_var,
            on_login=self._login_view_submit,
            on_create_account=self._show_create_account_view,
            on_settings=self._open_settings_modal,
        )
        self.connect_button = self.login_frame.login_button

    def _build_create_account_frame(self) -> None:
        self.create_account_frame = CreateAccountView(
            self.content_frame,
            account_id_var=self.create_account_id_var,
            password_var=self.create_account_password_var,
            password_confirm_var=self.create_account_password_confirm_var,
            nickname_var=self.create_account_nickname_var,
            on_create=self._create_account_view_submit,
            on_back=self._show_login_view,
        )

    def _show_create_account_view(self) -> None:
        if not self.state.connected or self._account_request_pending:
            return
        self._authentication_view = "create_account"
        self.message_var.set("Enter the account information.")
        self._render_view()
        self.create_account_frame.entries[0].focus_set()

    def _show_login_view(self) -> None:
        if self._account_request_pending:
            return
        self._authentication_view = "login"
        self.message_var.set("Log in to continue.")
        self._render_view()
        self.login_frame.account_id_entry.focus_set()

    def _login_view_submit(self) -> None:
        if (
            not self.state.connected
            or self.state.view_state != DISCONNECTED
            or self._login_request_pending
            or self._account_request_pending
        ):
            return
        try:
            account_id = normalize_account_id(self.login_account_id_var.get())
            password = validate_password(self.login_password_var.get())
        except ValueError as exc:
            self.message_var.set(str(exc))
            return
        self._login_request_pending = True
        self.login_account_id_var.set(account_id)
        self.network.login(account_id, password)
        self.message_var.set("Logging in...")
        self._render_controls()

    def _create_account_view_submit(self) -> None:
        if (
            not self.state.connected
            or self.state.view_state != DISCONNECTED
            or self._account_request_pending
        ):
            return
        try:
            account_id = normalize_account_id(self.create_account_id_var.get())
            password = validate_password(self.create_account_password_var.get())
            if password != self.create_account_password_confirm_var.get():
                raise ValueError("Password and Confirm Password do not match.")
            nickname = normalize_nickname(self.create_account_nickname_var.get())
        except ValueError as exc:
            self.message_var.set(str(exc))
            return

        self._account_request_pending = True
        self._pending_account_id = account_id
        self._pending_account_password = password
        self.create_account_id_var.set(account_id)
        self.network.create_account(account_id, password, nickname)
        self.message_var.set("Creating account...")
        self._render_controls()

    def _build_lobby_frame(self) -> None:
        self.lobby_frame = ttk.LabelFrame(self.content_frame, text="Lobby", padding=10)
        self.lobby_frame.rowconfigure(1, weight=1)
        self.lobby_frame.columnconfigure(0, weight=1)

        lobby_header = ttk.Frame(self.lobby_frame, padding=(0, 0, 0, 10))
        lobby_header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.create_room_button = ttk.Button(
            lobby_header, text="Create Room", command=self._create_room
        )
        self.create_room_button.pack(side="left")
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
            command=self._on_create_room_game_type_changed,
        )
        self.create_othello_radio = ttk.Radiobutton(
            self.create_room_modal_canvas,
            text="Othello",
            variable=self._create_room_game_type_var,
            value=GameType.OTHELLO.value,
            command=self._on_create_room_game_type_changed,
        )
        self.create_turn_time_radios: list[ttk.Radiobutton] = []
        for value in TURN_TIME_OPTIONS:
            label = "Infinite" if value == INFINITE_TURN_TIME else f"{value} sec"
            radio = ttk.Radiobutton(
                self.create_room_modal_canvas,
                text=label,
                variable=self._create_room_turn_time_var,
                value=value,
            )
            self.create_turn_time_radios.append(radio)
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
            *self.create_turn_time_radios,
            self.create_room_modal_cancel_button,
            self.create_room_modal_submit_button,
        ):
            widget.bind("<Escape>", lambda _event: self._close_create_room_modal())
        self.create_room_name_entry.bind(
            "<Return>", lambda _event: self._submit_create_room()
        )

        self.join_room_modal_canvas = tk.Canvas(
            self.lobby_frame,
            background="#6B6258",
            highlightthickness=0,
            takefocus=True,
        )
        self.join_room_modal_canvas.bind(
            "<Configure>", lambda _event: self._draw_join_room_modal()
        )
        self.join_room_modal_cancel_button = ttk.Button(
            self.join_room_modal_canvas,
            text="Cancel",
            command=self._close_join_room_modal,
        )
        self.join_room_modal_submit_button = ttk.Button(
            self.join_room_modal_canvas,
            text="Join",
            command=self._submit_join_room,
        )
        for widget in (
            self.join_room_modal_cancel_button,
            self.join_room_modal_submit_button,
        ):
            widget.bind("<Escape>", lambda _event: self._close_join_room_modal())

    def _build_game_frame(self) -> None:
        self.game_frame = ttk.Frame(self.content_frame)
        self.game_frame.rowconfigure(1, weight=1)
        self.game_frame.columnconfigure(0, weight=1)
        self.game_frame.columnconfigure(1, weight=0)

        room_header = ttk.Frame(self.game_frame, padding=(0, 0, 0, 7))
        room_header.grid(row=0, column=0, sticky="ew")
        room_header.columnconfigure(2, weight=1)
        self.turn_timer_widget = TurnTimerWidget(room_header)
        self.turn_timer_widget.grid(
            row=0, column=0, padx=(0, 8), sticky="w"
        )
        self.current_turn_widget = CurrentTurnWidget(room_header)
        self.current_turn_widget.grid(row=0, column=1, padx=(0, 14), sticky="w")

        self.control_slot = ttk.Frame(room_header)
        self.control_slot.grid(row=0, column=2, sticky="w")
        self.in_game_controls = ttk.Frame(self.control_slot)
        self.in_game_controls.grid(row=0, column=0, sticky="w")
        self.undo_button = ttk.Button(
            self.in_game_controls, text="무르기", command=self._request_undo
        )
        self.undo_button.pack(side="left")
        self.resign_button = ttk.Button(
            self.in_game_controls, text="기권", command=self._request_resign
        )
        self.resign_button.pack(side="left", padx=(7, 0))

        self.out_game_controls = ttk.Frame(self.control_slot)
        self.out_game_controls.grid(row=0, column=0, sticky="w")
        self.mode_toggle_button = ttk.Button(
            self.out_game_controls, text="Observer ↔ Player", command=self._toggle_role
        )
        self.mode_toggle_button.pack(side="left")
        self.ready_button = ttk.Button(
            self.out_game_controls, text="Ready", command=self._send_ready
        )
        self.ready_button.pack(side="left", padx=(7, 0))
        self.leave_room_button = ttk.Button(
            self.out_game_controls, text="Leave Room", command=self._leave_room
        )
        self.leave_room_button.pack(side="left", padx=(7, 0))

        self.canvas = tk.Canvas(
            self.game_frame,
            width=INITIAL_CANVAS_SIZE,
            height=INITIAL_CANVAS_SIZE,
            background="#D9A85C",
            highlightthickness=1,
            highlightbackground="#7B542B",
        )
        self.canvas.grid(row=1, column=0, pady=(7, 0), sticky="nsew")
        side_panel = ttk.Frame(self.game_frame)
        side_panel.grid(row=0, column=1, rowspan=2, padx=(7, 0), sticky="nsew")
        side_panel.columnconfigure(0, weight=1)
        side_panel.rowconfigure(0, weight=1)
        side_panel.rowconfigure(1, weight=1)
        self.room_member_list = RoomMemberList(side_panel)
        self.room_member_list.grid(row=0, column=0, sticky="nsew")
        self.chat_panel = ChatPanel(side_panel, on_send=self._send_chat_message)
        self.chat_panel.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.canvas.bind("<Button-1>", self._on_board_click)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.board_overlay = CanvasOverlay(self.canvas)
        self.undo_action_overlay = ActionModalOverlay(self.canvas)
        self.undo_blocking_overlay = SystemBlockingOverlay(self.canvas)
        self.resign_action_overlay = ActionModalOverlay(self.canvas)
        self.resign_blocking_overlay = SystemBlockingOverlay(self.canvas)
        self.ready_blocking_overlay = SystemBlockingOverlay(self.canvas)
        self.turn_timer = TurnTimer(self.root, self._set_turn_time_display)

    def _set_turn_time_display(self, text: str, warning: bool) -> None:
        """Apply presentation output from the display-only turn timer."""
        self.turn_timer_widget.set_display(text, warning)
        self._turn_timer_display_expired = text == "00:00"
        if self._turn_timer_display_expired:
            self._clear_hover()

    def _sync_turn_timer_from_state(self) -> None:
        if self.state.game_status != "PLAYING":
            self.turn_timer.deactivate()
            return
        self.turn_timer.synchronize(
            self.state.turn_time_limit_sec,
            self.state.turn_deadline_unix_ms,
            self.state.turn_revision,
        )

    def _open_settings_modal(self) -> None:
        if (
            self._connecting
            or self._settings_modal_open
            or self.state.view_state == IN_ROOM
            or self._login_request_pending
            or self._account_request_pending
        ):
            return
        self._settings_modal_open = True
        self._settings_server_var.set(self.server_var.get())
        self._settings_account_id_var.set(
            self.state.account_id or self.login_account_id_var.get() or "Not saved"
        )
        self._settings_auto_login_var.set(self.auto_login_var.get())
        self._settings_error_var.set("")
        self.settings_modal_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.settings_modal_canvas.tk.call("raise", self.settings_modal_canvas._w)
        self.root.update_idletasks()
        self._draw_settings_modal()
        if not self.state.connected:
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
        panel_height = 480
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
            text="Settings",
            fill="#3E2B18",
            font=("TkDefaultFont", 18, "bold"),
        )
        canvas.create_text(
            left + 32,
            top + 84,
            text="Network Settings",
            anchor="w",
            fill="#3E2B18",
            font=("TkDefaultFont", 12, "bold"),
        )
        canvas.create_text(
            left + 48, top + 116, text="Server URL", anchor="w",
            fill="#3E2B18", font=("TkDefaultFont", 10, "bold"),
        )
        canvas.create_window(
            center_x,
            top + 148,
            window=self.settings_server_entry,
            width=panel_width - 96,
        )
        canvas.create_line(
            left + 32, top + 174, right - 32, top + 174, fill="#D6C3A5"
        )
        canvas.create_text(
            left + 32, top + 196, text="Account Settings", anchor="w",
            fill="#3E2B18", font=("TkDefaultFont", 12, "bold"),
        )
        canvas.create_text(
            left + 48, top + 229, text="Account ID", anchor="w",
            fill="#3E2B18", font=("TkDefaultFont", 10, "bold"),
        )
        canvas.create_text(
            left + 150, top + 229, text=self._settings_account_id_var.get(),
            anchor="w", fill="#3E2B18", font=("TkDefaultFont", 10),
        )
        canvas.create_window(
            left + 150, top + 263, window=self.settings_auto_login_check,
            anchor="w",
        )
        canvas.create_line(
            left + 32, top + 289, right - 32, top + 289, fill="#D6C3A5"
        )
        canvas.create_text(
            left + 32, top + 311, text="Application Information", anchor="w",
            fill="#3E2B18", font=("TkDefaultFont", 12, "bold"),
        )
        canvas.create_window(
            center_x,
            bottom - 76,
            window=self.settings_modal_error_label,
            width=panel_width - 64,
        )
        canvas.create_text(
            left + 48,
            top + 345,
            text=f"Client Version    {CLIENT_VERSION}",
            anchor="w",
            fill="#76685A",
            font=("TkDefaultFont", 10, "bold"),
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
            server_url = (
                self.server_var.get()
                if self.state.connected
                else normalize_server_url(self._settings_server_var.get())
            )
            auto_login = self._settings_auto_login_var.get()
            account_id = self.state.account_id or self.login_account_id_var.get()
            if auto_login and (not account_id or not self.login_password_var.get()):
                raise ValueError("Auto Login requires saved login information.")
            save_client_settings(
                ClientSettings(
                    server_url=server_url,
                    account_id=account_id,
                    password=self.login_password_var.get(),
                    auto_login=auto_login,
                ),
                self._settings_path,
            )
        except (OSError, ValueError) as exc:
            self._settings_error_var.set(str(exc))
            return
        self.server_var.set(server_url)
        self.auto_login_var.set(auto_login)
        self._close_settings_modal()
        self.message_var.set("Settings saved.")

    def _close_settings_modal(self) -> None:
        if not self._settings_modal_open:
            return
        self._settings_modal_open = False
        self.settings_modal_canvas.place_forget()
        self.settings_modal_canvas.delete("all")
        self._settings_server_var.set(self.server_var.get())
        self._settings_account_id_var.set(
            self.state.account_id or self.login_account_id_var.get() or "Not saved"
        )
        self._settings_auto_login_var.set(self.auto_login_var.get())
        self._settings_error_var.set("")
        self._render_controls()

    def _disconnect(self) -> None:
        if not self.state.connected:
            return
        self.network.disconnect()
        self.lobby_disconnect_button.configure(state="disabled")
        self.message_var.set("Disconnecting...")

    def _connect_to_server(self) -> None:
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
            or self._join_room_modal_open
        ):
            return
        self._create_room_modal_open = True
        self._create_room_name_var.set("")
        self._create_room_error_var.set("")
        self._create_room_game_type_var.set(GameType.GOMOKU.value)
        self._create_room_turn_time_var.set(INFINITE_TURN_TIME)
        othello_supported = GameType.OTHELLO in self.state.supported_game_types
        self.create_othello_radio.configure(
            state="normal" if othello_supported else "disabled"
        )
        self._on_create_room_game_type_changed()
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
        panel_height = 430
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
        canvas.create_text(
            left + 30,
            top + 260,
            text="Turn Time",
            anchor="w",
            fill="#3E2B18",
            font=("TkDefaultFont", 10, "bold"),
            tags=("modal",),
        )
        for index, radio in enumerate(self.create_turn_time_radios):
            row, column = divmod(index, 3)
            canvas.create_window(
                left + 55 + column * 125,
                top + 292 + row * 34,
                window=radio,
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
            raw_turn_time = self._create_room_turn_time_var.get()
            turn_time_limit_sec = (
                None
                if raw_turn_time == INFINITE_TURN_TIME
                else int(raw_turn_time)
            )
            if game_type is GameType.OTHELLO and turn_time_limit_sec is not None:
                raise ValueError("오셀로는 착수 제한 시간을 지원하지 않습니다.")
        except ValueError as exc:
            self._create_room_error_var.set(str(exc))
            return
        self._room_request_pending = True
        self.network.create_room(room_name, game_type, turn_time_limit_sec)
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
        self._create_room_turn_time_var.set(INFINITE_TURN_TIME)
        self._render_controls()

    def _on_create_room_game_type_changed(self) -> None:
        is_gomoku = self._create_room_game_type_var.get() == GameType.GOMOKU.value
        if not is_gomoku:
            self._create_room_turn_time_var.set(INFINITE_TURN_TIME)
        state = "normal" if is_gomoku else "disabled"
        for radio in self.create_turn_time_radios:
            radio.configure(state=state)

    def _open_join_room_modal(self, room_id: str) -> None:
        room = next((item for item in self.state.rooms if item.room_id == room_id), None)
        if (
            self.state.view_state != LOBBY
            or self._room_request_pending
            or self._create_room_modal_open
            or self._join_room_modal_open
            or room is None
            or not room.can_join
        ):
            return
        self._join_room_modal_open = True
        self._join_room_id = room.room_id
        self._join_room_name = room.room_name
        self.join_room_modal_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.join_room_modal_canvas.tk.call("raise", self.join_room_modal_canvas._w)
        self.root.update_idletasks()
        self._draw_join_room_modal()
        self.join_room_modal_submit_button.focus_set()
        self._render_controls()

    def _draw_join_room_modal(self) -> None:
        if not self._join_room_modal_open:
            return
        canvas = self.join_room_modal_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 500)
        height = max(canvas.winfo_height(), 360)
        center_x = width / 2
        center_y = height / 2
        panel_width = min(460, width - 50)
        panel_height = 230
        left = center_x - panel_width / 2
        right = center_x + panel_width / 2
        top = center_y - panel_height / 2
        bottom = center_y + panel_height / 2
        canvas.create_rectangle(0, 0, width, height, fill="#6B6258", outline="")
        canvas.create_rectangle(
            left, top, right, bottom, fill="#FFF8EA",
            outline="#7B542B", width=3,
        )
        canvas.create_text(
            center_x, top + 44, text="Join Room", fill="#3E2B18",
            font=("TkDefaultFont", 18, "bold"),
        )
        canvas.create_text(
            center_x, top + 94, text=f"'{self._join_room_name}'",
            fill="#3E2B18", font=("TkDefaultFont", 11, "bold"),
        )
        canvas.create_text(
            center_x, top + 124, text="이 방에 입장하시겠습니까?",
            fill="#3E2B18", font=("TkDefaultFont", 10),
        )
        canvas.create_window(
            center_x - 48, bottom - 42,
            window=self.join_room_modal_cancel_button,
        )
        canvas.create_window(
            center_x + 48, bottom - 42,
            window=self.join_room_modal_submit_button,
        )

    def _submit_join_room(self) -> None:
        if (
            not self._join_room_modal_open
            or self._room_request_pending
            or self._join_room_id is None
        ):
            return
        self._room_request_pending = True
        self.network.join_room(self._join_room_id)
        self.message_var.set(f"Joining '{self._join_room_name}'...")
        self._render_controls()

    def _close_join_room_modal(self) -> None:
        if not self._join_room_modal_open or self._room_request_pending:
            return
        self._join_room_modal_open = False
        self._join_room_id = None
        self._join_room_name = ""
        self.join_room_modal_canvas.place_forget()
        self.join_room_modal_canvas.delete("all")
        self._render_controls()

    def _reset_join_room_modal(self) -> None:
        self._room_request_pending = False
        self._close_join_room_modal()

    def _leave_room(self) -> None:
        if (
            self.state.view_state != IN_ROOM
            or self._leave_pending
            or self.state.game_status == "PLAYING"
        ):
            return
        self._leave_pending = True
        self.network.leave_room()
        self.message_var.set("Leaving room... Waiting for server confirmation.")
        self._render_controls()

    def _send_ready(self) -> None:
        if (
            self.state.view_state != IN_ROOM
            or not self.state.connected
            or self.state.game_status not in {"WAITING", "FINISHED"}
            or self.state.my_role != PLAYER
            or self.state.player_count != 2
            or self.state.my_ready
            or self._ready_request_pending
            or self._undo_pending
        ):
            return
        self._ready_request_pending = True
        self.network.send_ready()
        self.message_var.set("Ready sent. Waiting for server confirmation...")
        self._render_controls()

    def _become_player(self) -> None:
        if (
            self.state.view_state != IN_ROOM
            or self.state.my_role != OBSERVER
            or self.state.game_status == "PLAYING"
            or self.state.player_count >= 2
            or self._role_change_pending
        ):
            return
        self._role_change_pending = True
        self.network.become_player()
        self.message_var.set("Requesting Player role...")
        self._render_controls()

    def _become_observer(self) -> None:
        if (
            self.state.view_state != IN_ROOM
            or self.state.my_role != PLAYER
            or self.state.game_status == "PLAYING"
            or self._role_change_pending
        ):
            return
        self._role_change_pending = True
        self.network.become_observer()
        self.message_var.set("Requesting Observer role...")
        self._render_controls()

    def _toggle_role(self) -> None:
        if self.state.my_role == OBSERVER:
            self._become_player()
        elif self.state.my_role == PLAYER:
            self._become_observer()

    def _request_undo(self) -> None:
        if (
            self.state.view_state != IN_ROOM
            or not self.state.connected
            or self.state.game_type is not GameType.GOMOKU
            or self.state.game_status != "PLAYING"
            or not self.state.has_accepted_move
            or self._undo_pending
        ):
            return
        self._undo_pending = True
        self._undo_waiting_for_game_state = False
        self._clear_hover()
        self.undo_blocking_overlay.show_blocking(
            "착수 되돌리기",
            "상대방의 응답을 기다리는 중입니다.",
        )
        self.network.request_undo()
        self.message_var.set("Undo requested. Waiting for opponent...")
        self._render_controls()

    def _respond_undo(self, accepted: bool) -> None:
        if not self._undo_pending or not self.undo_action_overlay.visible:
            return
        self.undo_action_overlay.set_actions_enabled(False)
        self.network.respond_undo(accepted)
        self.message_var.set("Undo response sent. Waiting for server...")

    def _send_chat_message(self, text: str) -> bool:
        """Validate the composer text and hand it to the network layer.

        Returns True when the message was sent so the composer can clear itself.
        The log is not touched here; it re-renders when the server echoes the
        message back as ``chat_message``.
        """
        if self.state.view_state != IN_ROOM or not self.state.connected:
            self.message_var.set("방에 입장한 뒤에 채팅할 수 있습니다.")
            return False
        try:
            normalized = normalize_chat_text(text)
        except ValueError as exc:
            self.message_var.set(str(exc))
            return False
        self.network.send_chat(normalized)
        return True

    def _request_resign(self) -> None:
        if (
            self.state.view_state != IN_ROOM
            or self.state.my_role != PLAYER
            or self.state.game_status != "PLAYING"
            or self._undo_pending
            or self._resign_pending
        ):
            return
        self._clear_hover()
        self.resign_action_overlay.show_actions(
            "기권",
            "정말 기권하시겠습니까?",
            (
                OverlayAction("기권", self._confirm_resign),
                OverlayAction("취소", self._cancel_resign),
            ),
            kind="warning",
            content_tag="resign_confirm_overlay",
        )

    def _confirm_resign(self) -> None:
        if self._resign_pending or not self.resign_action_overlay.visible:
            return
        self.resign_action_overlay.clear()
        self._resign_pending = True
        self.resign_blocking_overlay.show_blocking(
            "기권",
            "서버의 게임 종료 처리를 기다리는 중입니다.",
        )
        self.network.resign()
        self.message_var.set("Resignation sent. Waiting for server...")
        self._render_controls()

    def _cancel_resign(self) -> None:
        if self._resign_pending:
            return
        self.resign_action_overlay.clear()

    def _on_room_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        self.room_canvas.itemconfigure(self._room_grid_window, width=event.width)
        self._layout_room_cards(event.width)

    def _on_board_click(self, event: tk.Event[tk.Misc]) -> None:
        if self.resign_action_overlay.consume_click():
            return
        if self.resign_blocking_overlay.consume_click():
            return
        if self.undo_action_overlay.consume_click():
            return
        if self.ready_blocking_overlay.consume_click():
            return
        if self.undo_blocking_overlay.consume_click():
            return
        if self.board_overlay.consume_click():
            return
        if self._move_pending or self._turn_timer_display_expired:
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
                self._show_forbidden_popup(
                    f"{label} 자리입니다.\n다른 곳에 두세요."
                )
            elif self.state.board[y][x] is not None:
                self.message_var.set("That position is already occupied.")
            return
        self.network.send_move(x, y)
        self._move_pending = True
        self._clear_hover()
        self.message_var.set(f"Move ({x}, {y}) sent. Waiting for server...")

    def _on_mouse_move(self, event: tk.Event[tk.Misc]) -> None:
        if (
            self.undo_action_overlay.visible
            or self.resign_action_overlay.visible
            or self.resign_blocking_overlay.visible
            or self.ready_blocking_overlay.visible
            or self.undo_blocking_overlay.visible
            or self.board_overlay.visible
            or self._turn_timer_display_expired
        ):
            self._clear_hover()
            return
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
        self._account_request_pending = False
        self._login_request_pending = False
        self._pending_account_id = None
        self._pending_account_password = None
        self._room_request_pending = False
        self._leave_pending = False
        self._role_change_pending = False
        self._move_pending = False
        self._clear_ready_state()
        self._clear_undo_state()
        self._clear_resign_state()
        self._cancel_forbidden_flash()

    def _clear_ready_state(self) -> None:
        self._ready_request_pending = False
        self.ready_blocking_overlay.clear_from_system()

    def _clear_undo_state(self) -> None:
        self._undo_pending = False
        self._undo_waiting_for_game_state = False
        self.undo_action_overlay.clear()
        self.undo_blocking_overlay.clear_from_system()

    def _clear_resign_state(self) -> None:
        self._resign_pending = False
        self.resign_action_overlay.clear()
        self.resign_blocking_overlay.clear_from_system()

    def _show_forbidden_popup(self, message: str) -> None:
        self._clear_hover()
        self.board_overlay.show(
            OverlayOptions(
                title="착수 불가",
                message=message,
                kind="warning",
            ),
            on_dismiss=self._dismiss_forbidden_popup,
        )

    def _show_undo_result_popup(
        self, accepted: bool, requested_by_me: bool = False
    ) -> None:
        self._clear_hover()
        if accepted:
            message = "착수가 되돌려졌습니다."
        elif requested_by_me:
            message = "상대방이 되돌리기 요청을 거절했습니다."
        else:
            message = "되돌리기 요청을 거절했습니다."
        self.board_overlay.show(
            OverlayOptions(
                title="되돌리기 완료" if accepted else "되돌리기 거절",
                message=message,
                kind="info" if accepted else "warning",
                dismiss_on_click=True,
                dismiss_hint="클릭하면 닫힙니다",
                content_tag="undo_result_overlay",
            )
        )

    def _show_opponent_ready_popup(self) -> None:
        self._clear_hover()
        self.board_overlay.show(
            OverlayOptions(
                title="Player Ready",
                message="상대 플레이어가 Ready 상태입니다.",
                kind="info",
                dismiss_on_click=True,
                dismiss_hint="클릭하면 닫힙니다",
                content_tag="player_ready_overlay",
            )
        )

    def _dismiss_forbidden_popup(self) -> None:
        self._cancel_forbidden_flash()
        self.state.rejected_point = None
        if self.state.view_state == IN_ROOM:
            self._draw_board()

    def _dismiss_result_popup(self) -> None:
        self._result_popup_dismissed = True

    def _reset_board_popup(self) -> None:
        self.board_overlay.clear()
        self._clear_ready_state()
        self._clear_undo_state()
        self._clear_resign_state()
        self._result_popup_dismissed = False

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
            self.message_var.set("Connected. Waiting for lobby confirmation...")
        elif event.kind == "disconnected":
            self._connecting = False
            self._clear_hover()
            self.state.reset_connection()
            self._reset_board_popup()
            self._clear_pending_requests()
            self.turn_timer.deactivate()
            self.room_member_list.set_members((), ())
            self.chat_panel.clear()
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
        was_finished = self.state.is_finished
        if message_type in {
            "joined",
            "left_room",
            "game_start",
            "move_result",
            "game_over",
            "game_state",
            "player_disconnected",
            "player_ready",
            "ready_confirmed",
            "role_changed",
            "room_members",
            "undo_requested",
            "undo_result",
            "turn_timeout",
        }:
            self._clear_hover()
        try:
            change = self.state.apply_server_message(payload)
        except ValueError as exc:
            LOGGER.warning("Rejected server message: %s", exc)
            self.message_var.set(f"Invalid server message: {exc}")
            return

        is_forbidden_error = (
            message_type == "error" and payload.get("code") == "FORBIDDEN_MOVE"
        )
        if message_type in {"room_list", "chat_message"}:
            pass
        elif is_forbidden_error:
            self.message_var.set(self.state.turn_message())
        else:
            self.message_var.set(change.message)
        if message_type == "connected":
            self._connecting = False
            self._authentication_view = "login"
            self.message_var.set("Connected. Log in to continue.")
            if (
                self.auto_login_var.get()
                and self.login_account_id_var.get()
                and self.login_password_var.get()
            ):
                self._login_view_submit()
        elif message_type == "account_created":
            account_id = self._pending_account_id or str(payload.get("account_id", ""))
            password = self._pending_account_password or ""
            self.login_account_id_var.set(account_id)
            self.login_password_var.set(password)
            self._account_request_pending = False
            self._pending_account_id = None
            self._pending_account_password = None
            self.create_account_id_var.set("")
            self.create_account_password_var.set("")
            self.create_account_password_confirm_var.set("")
            self.create_account_nickname_var.set("")
            self._authentication_view = "login"
            self.message_var.set("Account created. Log in with the new account.")
        elif message_type == "login_succeeded":
            self._login_request_pending = False
            try:
                save_client_settings(
                    ClientSettings(
                        server_url=self.server_var.get(),
                        account_id=self.login_account_id_var.get(),
                        password=self.login_password_var.get(),
                        auto_login=self.auto_login_var.get(),
                    ),
                    self._settings_path,
                )
            except (OSError, ValueError) as exc:
                LOGGER.warning("Could not save login settings: %s", exc)
                self.message_var.set(f"Logged in, but settings were not saved: {exc}")
            self.network.request_room_list()
        elif message_type == "room_list":
            self._render_room_list()
        elif message_type == "joined":
            self._reset_join_room_modal()
            self._reset_board_popup()
            self._room_request_pending = False
            self._leave_pending = False
            self._ready_request_pending = False
            self._role_change_pending = False
            self._move_pending = False
            self.turn_timer.deactivate()
            self.room_member_list.set_members((), ())
            self.chat_panel.clear()
        elif message_type == "left_room":
            self._reset_board_popup()
            self._leave_pending = False
            self._ready_request_pending = False
            self._role_change_pending = False
            self._move_pending = False
            self.turn_timer.deactivate()
            self.room_member_list.set_members((), ())
            self.chat_panel.clear()
            self.network.request_room_list()
        elif message_type == "error":
            self._clear_pending_requests()
            self._reset_join_room_modal()
            self._sync_forbidden_flash()
            if is_forbidden_error:
                self._show_forbidden_popup(change.message)
        elif message_type == "game_start":
            self._reset_board_popup()
            self._sync_turn_timer_from_state()
        elif message_type == "player_disconnected":
            self._reset_board_popup()
            self.turn_timer.deactivate()
        elif message_type == "role_changed":
            self._role_change_pending = False
            self._clear_ready_state()
            self.board_overlay.clear()
        elif message_type == "room_members":
            self.room_member_list.set_members(
                self.state.player_members, self.state.observer_members
            )
            if not self.state.my_ready:
                self.ready_blocking_overlay.clear_from_system()
        elif message_type == "chat_message":
            self.chat_panel.set_messages(self.state.chat_messages)
        elif message_type == "ready_confirmed":
            self._ready_request_pending = False
            if self.state.is_finished:
                self._result_popup_dismissed = True
                self.board_overlay.clear()
            self.ready_blocking_overlay.show_blocking(
                "Ready",
                "상대 플레이어의 Ready를 기다리고 있습니다.",
            )
        elif message_type == "player_ready":
            if self.state.is_finished:
                self._result_popup_dismissed = True
                self.board_overlay.clear()
            self._show_opponent_ready_popup()
        elif message_type in {"move_result", "game_state", "game_over"}:
            self._move_pending = False
            if message_type == "game_state" and self._undo_waiting_for_game_state:
                self._clear_undo_state()
                self._show_undo_result_popup(accepted=True)
            if self.state.is_finished and not was_finished:
                self._result_popup_dismissed = False
            if message_type == "move_result" and self.board_overlay.kind == "warning":
                self.board_overlay.clear()
            if message_type == "game_state":
                self._sync_turn_timer_from_state()
            elif message_type == "game_over":
                self._clear_resign_state()
                self.turn_timer.deactivate()
        elif message_type == "turn_timeout":
            self._move_pending = False
            self.turn_timer.synchronize(
                self.state.turn_time_limit_sec,
                None,
                self.state.turn_revision,
            )
        elif message_type == "undo_requested":
            self._undo_pending = True
            self._undo_waiting_for_game_state = False
            self.turn_timer.pause()
            requester_color = payload.get("requester_color")
            if requester_color == self.state.my_color:
                self.undo_action_overlay.clear()
                self.undo_blocking_overlay.show_blocking(
                    "착수 되돌리기",
                    "상대방의 응답을 기다리는 중입니다.",
                )
            else:
                undo_count = payload.get("undo_count")
                self.undo_blocking_overlay.clear_from_system()
                self.undo_action_overlay.show_actions(
                    "착수 되돌리기 요청",
                    f"상대방이 {undo_count}수 되돌리기를 요청했습니다.",
                    (
                        OverlayAction("수락", lambda: self._respond_undo(True)),
                        OverlayAction("거절", lambda: self._respond_undo(False)),
                    ),
                    kind="warning",
                )
        elif message_type == "undo_result":
            accepted = payload.get("accepted") is True
            self.turn_timer.pause()
            self.undo_action_overlay.clear()
            if accepted:
                self._undo_pending = True
                self._undo_waiting_for_game_state = True
                self.undo_blocking_overlay.show_blocking(
                    "착수 되돌리기",
                    "변경된 대국 상태를 동기화하는 중입니다.",
                )
            else:
                self._clear_undo_state()
                self._show_undo_result_popup(
                    accepted=False,
                    requested_by_me=payload.get("requester_color") == self.state.my_color,
                )
        if change.redraw_board and self.state.view_state == IN_ROOM:
            self._draw_board()
        if not change.handled:
            LOGGER.warning(change.message)

    def _render_view(self) -> None:
        for frame in (
            self.connection_frame,
            self.login_frame,
            self.create_account_frame,
            self.lobby_frame,
            self.game_frame,
        ):
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
            if not self.state.connected or self._authentication_view == "connection":
                authentication_frame = self.connection_frame
            elif self._authentication_view == "create_account":
                authentication_frame = self.create_account_frame
            else:
                authentication_frame = self.login_frame
            authentication_frame.grid(row=0, column=0, sticky="nsew")
        if self.state.view_state != LOBBY:
            self._close_create_room_modal()
            self._reset_join_room_modal()
        if self.state.view_state == IN_ROOM:
            self._close_settings_modal()
        self._render_controls()

    def _render_room_list(self) -> None:
        if (
            self._join_room_modal_open
            and self._join_room_id not in {room.room_id for room in self.state.rooms}
            and not self._room_request_pending
        ):
            self._reset_join_room_modal()
        for card in self.room_cards.values():
            card.destroy()
        self.room_cards.clear()
        for room in self.state.rooms:
            timer_text = self._room_timer_text(room)
            card = tk.Button(
                self.room_grid,
                text=(
                    f"{room.room_name}\n"
                    f"{room.game_type.label} · {room.board_size} × {room.board_size}"
                    f"{timer_text}\n"
                    f"Members {room.players}/{room.max_players} · {room.status}\n"
                    f"Players {room.player_count}/{room.max_game_players} · "
                    f"Observers {room.observer_count}"
                ),
                image=self._stone_images[BLACK],
                compound="top",
                command=lambda room_id=room.room_id: self._open_join_room_modal(room_id),
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
            self.room_cards[room.room_id] = card
        self._layout_room_cards(self.room_canvas.winfo_width())
        self._render_controls()

    @staticmethod
    def _room_timer_text(room: RoomSummary) -> str:
        if room.game_type is not GameType.GOMOKU:
            return ""
        if room.turn_time_limit_sec is None:
            return " · Infinite"
        return f" · {room.turn_time_limit_sec} sec"

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

    def _render_status(self) -> None:
        self.current_turn_widget.set_color(self.state.current_turn)
        self._render_controls()

    def _render_controls(self) -> None:
        authentication_available = (
            self.state.connected
            and self.state.view_state == DISCONNECTED
            and not self._account_request_pending
            and not self._login_request_pending
            and not self._settings_modal_open
        )
        self.connect_button.configure(
            text="Login",
            state="normal" if authentication_available else "disabled",
        )
        self.settings_button.configure(
            state="normal"
            if not self.state.connected and not self._connecting
            else "disabled"
        )
        self.login_frame.settings_button.configure(
            state="normal" if authentication_available else "disabled"
        )
        in_lobby = self.state.connected and self.state.view_state == LOBBY
        lobby_available = (
            in_lobby
            and self.state.authenticated
            and self.state.account_id is not None
            and self.state.account_nickname is not None
            and not self._create_room_modal_open
            and not self._join_room_modal_open
        )
        self.connection_frame.retry_button.configure(
            state="normal"
            if not self.state.connected and not self._connecting
            else "disabled"
        )
        self.login_frame.account_id_entry.configure(
            state="normal" if authentication_available else "disabled"
        )
        self.login_frame.password_entry.configure(
            state="normal" if authentication_available else "disabled"
        )
        self.login_frame.auto_login_check.configure(
            state="normal" if authentication_available else "disabled"
        )
        self.login_frame.create_account_button.configure(
            state="normal" if authentication_available else "disabled"
        )
        for entry in self.create_account_frame.entries:
            entry.configure(
                state="normal" if authentication_available else "disabled"
            )
        self.create_account_frame.back_button.configure(
            state="normal" if authentication_available else "disabled"
        )
        self.create_account_frame.create_button.configure(
            state="normal" if authentication_available else "disabled"
        )
        self.create_room_button.configure(
            state="normal"
            if lobby_available and not self._room_request_pending
            else "disabled"
        )
        disconnect_state = "normal" if self.state.connected else "disabled"
        self.lobby_disconnect_button.configure(
            state=disconnect_state
            if not self._create_room_modal_open and not self._join_room_modal_open
            else "disabled"
        )
        self.settings_server_entry.configure(
            state="disabled" if self.state.connected else "normal"
        )
        self.settings_auto_login_check.configure(
            state="normal" if self._settings_modal_open else "disabled"
        )
        for card in self.room_cards.values():
            card.configure(
                state="disabled"
                if self._create_room_modal_open or self._join_room_modal_open
                else "normal"
            )
        join_action_state = (
            "normal"
            if self._join_room_modal_open and not self._room_request_pending
            else "disabled"
        )
        self.join_room_modal_cancel_button.configure(state=join_action_state)
        self.join_room_modal_submit_button.configure(state=join_action_state)
        self.leave_room_button.configure(
            state="normal"
            if (
                self.state.view_state == IN_ROOM
                and not self._leave_pending
                and self.state.game_status in {"WAITING", "FINISHED"}
            )
            else "disabled"
        )
        can_ready = (
            self.state.view_state == IN_ROOM
            and self.state.connected
            and self.state.game_status in {"WAITING", "FINISHED"}
            and self.state.my_role == PLAYER
            and self.state.player_count == 2
            and not self.state.my_ready
            and not self._ready_request_pending
            and not self._undo_pending
        )
        self.ready_button.configure(state="normal" if can_ready else "disabled")
        can_become_player = (
            self.state.view_state == IN_ROOM
            and self.state.connected
            and self.state.my_role == OBSERVER
            and self.state.game_status != "PLAYING"
            and self.state.player_count < 2
            and not self._role_change_pending
        )
        can_become_observer = (
            self.state.view_state == IN_ROOM
            and self.state.connected
            and self.state.my_role == PLAYER
            and self.state.game_status != "PLAYING"
            and not self._role_change_pending
        )
        can_toggle_role = can_become_player or can_become_observer
        toggle_text = (
            "Observer → Player"
            if self.state.my_role == OBSERVER
            else "Player → Observer"
            if self.state.my_role == PLAYER
            else "Observer ↔ Player"
        )
        self.mode_toggle_button.configure(
            text=toggle_text,
            state="normal" if can_toggle_role else "disabled",
        )
        can_undo = (
            self.state.view_state == IN_ROOM
            and self.state.connected
            and self.state.game_type is GameType.GOMOKU
            and self.state.my_role == PLAYER
            and self.state.game_status == "PLAYING"
            and self.state.has_accepted_move
            and not self._undo_pending
        )
        self.undo_button.configure(state="normal" if can_undo else "disabled")
        can_resign = (
            self.state.view_state == IN_ROOM
            and self.state.connected
            and self.state.my_role == PLAYER
            and self.state.game_status == "PLAYING"
            and not self._undo_pending
            and not self._resign_pending
        )
        self.resign_button.configure(state="normal" if can_resign else "disabled")
        self.chat_panel.set_enabled(
            self.state.view_state == IN_ROOM and self.state.connected
        )
        if self.state.game_status == "PLAYING":
            self.out_game_controls.grid_remove()
            self.in_game_controls.grid()
        else:
            self.in_game_controls.grid_remove()
            self.out_game_controls.grid()

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
        self._render_preview(geometry)
        self._render_board_overlay()

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
        if (
            coordinate is None
            or self._move_pending
            or self._turn_timer_display_expired
            or not self.state.can_move(*coordinate)
        ):
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

    def _render_board_overlay(self) -> None:
        if self.state.is_finished and not self._result_popup_dismissed:
            self.board_overlay.show(
                OverlayOptions(
                    title="게임 종료",
                    message=self.state.build_game_over_message(),
                    kind="result",
                    content_tag="result_overlay",
                ),
                on_dismiss=self._dismiss_result_popup,
            )
        else:
            self.board_overlay.redraw()
        self.ready_blocking_overlay.redraw()
        self.undo_blocking_overlay.redraw()
        self.undo_action_overlay.redraw()
        self.resign_blocking_overlay.redraw()
        self.resign_action_overlay.redraw()

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
        self.board_overlay.clear()
        self._clear_ready_state()
        self._clear_undo_state()
        self._clear_resign_state()
        self.turn_timer.close()
        self.network.shutdown()
        self.root.destroy()
