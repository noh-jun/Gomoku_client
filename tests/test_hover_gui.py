from pathlib import Path
import tempfile
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import unittest

from omok_client.gui import OmokApp
from omok_client.game_type import GameType
from omok_client.network import NetworkEvent
from omok_client.state import AppState, BLACK, IN_ROOM, WHITE


def label_image_name(label: ttk.Label) -> str:
    value = label.cget("image")
    if isinstance(value, tuple):
        return str(value[0]) if value else ""
    return str(value)


class HoverGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.temp_directory = tempfile.TemporaryDirectory()
        self.settings_path = Path(self.temp_directory.name) / "client_settings.json"
        self.app = OmokApp(self.root, settings_path=self.settings_path)
        self.app.canvas.configure(width=800, height=700)
        self.root.update_idletasks()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            self.app._on_close()
        if hasattr(self, "temp_directory"):
            self.temp_directory.cleanup()

    def enter_lobby(self) -> None:
        self.app._handle_network_event(NetworkEvent("connected", message="Connected."))
        self.app.network.request_room_list = lambda: None
        self.app._handle_network_event(NetworkEvent("message", payload={"type": "connected"}))

    def test_connection_lobby_and_game_are_separate_pages(self) -> None:
        self.assertEqual(self.app.connection_frame.winfo_manager(), "grid")
        self.assertFalse(hasattr(self.app, "server_entry"))
        self.assertEqual(self.app.connect_button.winfo_manager(), "grid")
        self.assertEqual(self.app.settings_button.winfo_manager(), "grid")
        self.assertEqual(self.app.lobby_frame.winfo_manager(), "")
        self.assertEqual(self.app.game_frame.winfo_manager(), "")

        self.app._handle_network_event(NetworkEvent("connected", message="Connected."))
        self.assertEqual(self.app.connection_frame.winfo_manager(), "grid")
        self.assertEqual(str(self.app.connect_button["state"]), "disabled")

        self.app.network.request_room_list = lambda: None
        self.app._handle_network_event(NetworkEvent("message", payload={"type": "connected"}))
        self.assertEqual(self.app.connection_frame.winfo_manager(), "")
        self.assertEqual(self.app.lobby_frame.winfo_manager(), "grid")
        self.assertEqual(self.app.game_frame.winfo_manager(), "")

        self.app._handle_network_event(NetworkEvent("disconnected", message="Disconnected."))
        self.assertEqual(self.app.connection_frame.winfo_manager(), "grid")
        self.assertEqual(self.app.lobby_frame.winfo_manager(), "")
        self.assertEqual(str(self.app.connect_button["state"]), "normal")

    def test_connection_settings_canvas_saves_and_cancel_discards(self) -> None:
        original_url = self.app.server_var.get()
        self.app._open_settings_modal()
        self.assertTrue(self.app._settings_modal_open)
        self.assertEqual(self.app.settings_modal_canvas.winfo_manager(), "place")
        self.assertEqual(str(self.app.connect_button["state"]), "disabled")

        self.app._settings_server_var.set("ws://10.0.0.2:9000")
        self.app._close_settings_modal()
        self.assertEqual(self.app.server_var.get(), original_url)
        self.assertFalse(self.settings_path.exists())

        self.app._open_settings_modal()
        self.app._settings_server_var.set("http://invalid.example")
        self.app._save_settings()
        self.assertTrue(self.app._settings_modal_open)
        self.assertIn("ws://", self.app._settings_error_var.get())

        self.app._settings_server_var.set("  ws://10.0.0.2:9000/  ")
        self.app._save_settings()
        self.assertFalse(self.app._settings_modal_open)
        self.assertEqual(self.app.server_var.get(), "ws://10.0.0.2:9000")
        self.assertIn("10.0.0.2", self.settings_path.read_text(encoding="utf-8"))

    def test_you_and_turn_use_stone_images_instead_of_text(self) -> None:
        empty_image = str(self.app._stone_images[None])
        black_image = str(self.app._stone_images[BLACK])
        white_image = str(self.app._stone_images[WHITE])
        self.assertNotEqual(black_image, white_image)
        self.assertEqual(label_image_name(self.app.you_stone_label), empty_image)
        self.assertEqual(label_image_name(self.app.turn_stone_label), empty_image)

        self.app.state = AppState(
            view_state=IN_ROOM,
            my_color=BLACK,
            current_turn=WHITE,
            game_status="PLAYING",
            connected=True,
        )
        self.app._render_status()
        self.assertEqual(label_image_name(self.app.you_stone_label), black_image)
        self.assertEqual(label_image_name(self.app.turn_stone_label), white_image)

    def test_lobby_room_list_selection_and_snapshot_refresh(self) -> None:
        self.enter_lobby()
        self.assertEqual(self.app.lobby_frame.winfo_manager(), "grid")
        self.assertEqual(self.app.game_frame.winfo_manager(), "")

        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "room_list",
                    "rooms": [
                        {
                            "room_id": "room_001",
                            "room_name": "초보 환영",
                            "board_size": 19,
                            "players": 1,
                            "max_players": 2,
                            "status": "WAITING",
                        },
                        {
                            "room_id": "room_002",
                            "room_name": "고수 대국",
                            "board_size": 15,
                            "players": 2,
                            "max_players": 2,
                            "status": "PLAYING",
                        },
                    ],
                },
            )
        )
        self.assertEqual(tuple(self.app.room_cards), ("room_001", "room_002"))
        self.assertIn("초보 환영", str(self.app.room_cards["room_001"]["text"]))
        self.assertNotIn("room_001", str(self.app.room_cards["room_001"]["text"]))
        self.app._layout_room_cards(440)
        self.assertEqual(int(self.app.room_cards["room_002"].grid_info()["column"]), 1)
        self.app._layout_room_cards(219)
        self.assertEqual(int(self.app.room_cards["room_002"].grid_info()["row"]), 1)
        self.app._select_room("room_001")
        self.assertEqual(str(self.app.join_room_button["state"]), "normal")
        self.assertEqual(str(self.app.room_cards["room_001"]["relief"]), "sunken")

        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "room_list",
                    "rooms": [
                        {
                            "room_id": "room_002",
                            "room_name": "고수 대국",
                            "board_size": 15,
                            "players": 2,
                            "max_players": 2,
                            "status": "PLAYING",
                        },
                        {
                            "room_id": "room_001",
                            "room_name": "초보 환영",
                            "board_size": 19,
                            "players": 1,
                            "max_players": 2,
                            "status": "WAITING",
                        },
                    ],
                },
            )
        )
        self.assertEqual(self.app._selected_room_id, "room_001")
        self.app._select_room("room_002")
        self.assertEqual(str(self.app.join_room_button["state"]), "disabled")

    def test_join_and_leave_wait_for_server_confirmation(self) -> None:
        self.enter_lobby()
        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "room_list",
                    "rooms": [
                        {
                            "room_id": "room_001",
                            "room_name": "친선 대국",
                            "board_size": 19,
                            "players": 1,
                            "max_players": 2,
                            "status": "WAITING",
                        }
                    ],
                },
            )
        )
        joined_requests: list[str] = []
        self.app.network.join_room = joined_requests.append
        self.app._select_room("room_001")
        self.app._join_selected_room()
        self.assertEqual(joined_requests, ["room_001"])
        self.assertEqual(self.app.message_var.get(), "Joining '친선 대국'...")
        self.assertEqual(self.app.state.view_state, "LOBBY")
        self.assertTrue(self.app._room_request_pending)

        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "joined",
                    "room_id": "room_001",
                    "room_name": "친선 대국",
                    "your_color": WHITE,
                    "board_size": 19,
                    "win_length": 5,
                },
            )
        )
        self.assertEqual(self.app.state.view_state, IN_ROOM)
        self.assertEqual(self.app.room_var.get(), "친선 대국")
        self.assertEqual(self.app.game_frame.winfo_manager(), "grid")

        leave_requests: list[bool] = []
        self.app.network.leave_room = lambda: leave_requests.append(True)
        self.app.network.request_room_list = lambda: None
        self.app._leave_room()
        self.assertEqual(leave_requests, [True])
        self.assertEqual(self.app.state.view_state, IN_ROOM)
        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={"type": "left_room", "room_id": "room_001"},
            )
        )
        self.assertEqual(self.app.state.view_state, "LOBBY")
        self.assertEqual(self.app.lobby_frame.winfo_manager(), "grid")
        self.assertIsNone(self.app.state.my_color)
        self.assertEqual(self.app.canvas.find_all(), ())

    def test_create_room_suppresses_duplicate_clicks_until_joined_or_error(self) -> None:
        self.enter_lobby()
        requests: list[tuple[str, GameType]] = []
        self.app.network.create_room = lambda name, game_type: requests.append(
            (name, game_type)
        )
        self.app._create_room()
        self.assertTrue(self.app._create_room_modal_open)
        self.assertEqual(
            self.app._create_room_game_type_var.get(), GameType.GOMOKU.value
        )
        self.assertEqual(self.app.create_room_modal_canvas.winfo_manager(), "place")
        self.assertEqual(self.app.create_room_modal_canvas.winfo_class(), "Canvas")
        self.assertEqual(str(self.app.refresh_rooms_button["state"]), "disabled")
        self.app._create_room()
        self.assertTrue(self.app._create_room_modal_open)
        self.assertEqual(requests, [])

        self.app._create_room_name_var.set("   ")
        self.app._submit_create_room()
        self.assertEqual(requests, [])
        self.assertIn("입력", self.app._create_room_error_var.get())

        self.app._create_room_name_var.set("  친선 대국  ")
        self.app._submit_create_room()
        self.assertEqual(requests, [("친선 대국", GameType.GOMOKU)])
        self.assertFalse(self.app._create_room_modal_open)
        self.assertEqual(self.app.create_room_modal_canvas.winfo_manager(), "")
        self.assertTrue(self.app._room_request_pending)
        self.assertEqual(self.app.state.view_state, "LOBBY")

        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "error",
                    "code": "ROOM_FULL",
                    "message": "Room full.",
                },
            )
        )
        self.assertFalse(self.app._room_request_pending)
        self.assertEqual(self.app.state.view_state, "LOBBY")

    def test_create_othello_room_and_render_othello_card(self) -> None:
        self.app._handle_network_event(NetworkEvent("connected", message="Connected."))
        self.app.network.request_room_list = lambda: None
        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "connected",
                    "supported_game_types": ["GOMOKU", "OTHELLO"],
                },
            )
        )
        requests: list[tuple[str, GameType]] = []
        self.app.network.create_room = lambda name, game_type: requests.append(
            (name, game_type)
        )
        self.app._create_room()
        self.app._create_room_name_var.set("친선 오셀로")
        self.app._create_room_game_type_var.set(GameType.OTHELLO.value)
        self.app._submit_create_room()
        self.assertEqual(requests, [("친선 오셀로", GameType.OTHELLO)])

        self.app._room_request_pending = False
        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "room_list",
                    "rooms": [
                        {
                            "room_id": "room_002",
                            "room_name": "친선 오셀로",
                            "game_type": "OTHELLO",
                            "board_size": 8,
                            "win_length": None,
                            "players": 1,
                            "max_players": 2,
                            "status": "WAITING",
                        }
                    ],
                },
            )
        )
        self.assertIn("Othello · 8 × 8", str(self.app.room_cards["room_002"]["text"]))

    def test_othello_uses_cell_renderer_legal_moves_score_and_pending(self) -> None:
        board = [[None for _ in range(8)] for _ in range(8)]
        board[3][3] = WHITE
        board[3][4] = BLACK
        board[4][3] = BLACK
        board[4][4] = WHITE
        self.app.state = AppState(
            view_state=IN_ROOM,
            game_type=GameType.OTHELLO,
            my_color=BLACK,
            starting_color=BLACK,
            board_size=8,
            win_length=None,
            board=board,
            current_turn=BLACK,
            game_status="PLAYING",
            connected=True,
            legal_moves={(2, 3)},
            score={BLACK: 2, WHITE: 2},
        )
        self.app._render_status()
        self.app._draw_board()
        self.assertEqual(self.app.game_type_var.get(), "Othello")
        self.assertEqual(self.app.score_var.get(), "Score: Black 2 · White 2")
        self.assertEqual(len(self.app.canvas.find_withtag("legal_move")), 1)
        self.assertEqual(str(self.app.canvas["background"]), "#2E7D32")

        legal_x, legal_y = self.app._geometry().board_to_pixel(2, 3)
        legal_event = SimpleNamespace(x=legal_x, y=legal_y)
        self.app._on_mouse_move(legal_event)  # type: ignore[arg-type]
        self.assertEqual(self.app.hover_position, (2, 3))
        sent: list[tuple[int, int]] = []
        self.app.network.send_move = lambda x, y: sent.append((x, y))
        self.app._on_board_click(legal_event)  # type: ignore[arg-type]
        self.app._on_board_click(legal_event)  # type: ignore[arg-type]
        self.assertEqual(sent, [(2, 3)])
        self.assertTrue(self.app._move_pending)

        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "move_result",
                    "game_type": "OTHELLO",
                    "x": 2,
                    "y": 3,
                    "color": BLACK,
                    "flipped": [{"x": 3, "y": 3, "color": BLACK}],
                    "passed_color": WHITE,
                    "next_turn": BLACK,
                },
            )
        )
        self.assertFalse(self.app._move_pending)
        self.assertIn("White has no legal move", self.app.message_var.get())
        nonlegal_x, nonlegal_y = self.app._geometry().board_to_pixel(0, 0)
        self.app._on_mouse_move(
            SimpleNamespace(x=nonlegal_x, y=nonlegal_y)  # type: ignore[arg-type]
        )
        self.assertIsNone(self.app.hover_position)

        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "game_over",
                    "game_type": "OTHELLO",
                    "winner": BLACK,
                    "loser": WHITE,
                    "reason": "no_legal_moves",
                    "score": {BLACK: 35, WHITE: 29},
                },
            )
        )
        overlay_text = next(
            item
            for item in self.app.canvas.find_withtag("result_overlay")
            if self.app.canvas.type(item) == "text"
        )
        self.assertEqual(
            self.app.canvas.itemcget(overlay_text, "text"),
            "You Win\nBlack 35 · White 29",
        )

    def test_hover_and_click_share_coordinates_for_15_and_19(self) -> None:
        for board_size, coordinate, color in (
            (15, (7, 7), BLACK),
            (19, (18, 18), WHITE),
        ):
            with self.subTest(board_size=board_size):
                self.app._move_pending = False
                self.app.state = AppState(
                    view_state=IN_ROOM,
                    my_color=color,
                    board_size=board_size,
                    current_turn=color,
                    game_status="PLAYING",
                    connected=True,
                )
                self.app._draw_board()
                pixel_x, pixel_y = self.app._geometry().board_to_pixel(*coordinate)
                event = SimpleNamespace(x=pixel_x, y=pixel_y)
                self.app._on_mouse_move(event)  # type: ignore[arg-type]
                self.assertEqual(self.app.hover_position, coordinate)
                self.assertIsNotNone(self.app._preview_item_id)

                sent: list[tuple[int, int]] = []
                self.app.network.send_move = lambda x, y: sent.append((x, y))
                self.app._on_board_click(event)  # type: ignore[arg-type]
                self.assertEqual(sent, [coordinate])
                self.assertIsNone(self.app.hover_position)

    def test_board_visibility_tracks_connection_state(self) -> None:
        self.app._draw_board()
        self.assertEqual(self.app.canvas.find_all(), ())

        self.app._handle_network_event(NetworkEvent("connected", message="Connected."))
        self.assertEqual(self.app.canvas.find_all(), ())
        self.app.network.request_room_list = lambda: None
        self.app._handle_network_event(
            NetworkEvent("message", payload={"type": "connected"})
        )
        self.assertEqual(self.app.state.view_state, "LOBBY")
        self.assertEqual(self.app.canvas.find_all(), ())
        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "joined",
                    "room_id": "room_001",
                    "your_color": BLACK,
                    "board_size": 15,
                    "win_length": 5,
                },
            )
        )
        line_count = sum(
            self.app.canvas.type(item) == "line" for item in self.app.canvas.find_all()
        )
        self.assertEqual(line_count, self.app.state.board_size * 2)

        self.app._handle_network_event(NetworkEvent("disconnected", message="Disconnected."))
        self.assertEqual(self.app.canvas.find_all(), ())

    def test_hover_is_hidden_when_move_is_not_allowed(self) -> None:
        self.app.state = AppState(
            view_state=IN_ROOM,
            my_color=BLACK,
            current_turn=BLACK,
            game_status="PLAYING",
            connected=True,
        )
        pixel_x, pixel_y = self.app._geometry().board_to_pixel(7, 7)
        event = SimpleNamespace(x=pixel_x, y=pixel_y)

        self.app.state.board[7][7] = WHITE
        self.app._on_mouse_move(event)  # type: ignore[arg-type]
        self.assertIsNone(self.app.hover_position)

        self.app.state.board[7][7] = None
        self.app.state.current_turn = WHITE
        self.app._on_mouse_move(event)  # type: ignore[arg-type]
        self.assertIsNone(self.app.hover_position)

        self.app.state.current_turn = BLACK
        self.app.state.game_status = "FINISHED"
        self.app._on_mouse_move(event)  # type: ignore[arg-type]
        self.assertIsNone(self.app.hover_position)

    def test_resize_repositions_preview_from_logical_coordinate(self) -> None:
        self.app.state = AppState(
            view_state=IN_ROOM,
            my_color=BLACK,
            board_size=19,
            current_turn=BLACK,
            game_status="PLAYING",
            connected=True,
        )
        coordinate = (9, 9)
        pixel_x, pixel_y = self.app._geometry().board_to_pixel(*coordinate)
        self.app._on_mouse_move(SimpleNamespace(x=pixel_x, y=pixel_y))  # type: ignore[arg-type]

        self.app.canvas.configure(width=640, height=820)
        self.root.update_idletasks()
        self.app._draw_board()

        self.assertEqual(self.app.hover_position, coordinate)
        preview_bounds = self.app.canvas.coords(self.app._preview_item_id)
        center_x = (preview_bounds[0] + preview_bounds[2]) / 2
        center_y = (preview_bounds[1] + preview_bounds[3]) / 2
        expected_x, expected_y = self.app._geometry().board_to_pixel(*coordinate)
        self.assertAlmostEqual(center_x, expected_x)
        self.assertAlmostEqual(center_y, expected_y)

    def test_game_over_clears_hover_and_restart_applies_new_color(self) -> None:
        self.app.state = AppState(
            view_state=IN_ROOM,
            my_color=BLACK,
            current_turn=BLACK,
            game_status="PLAYING",
            connected=True,
        )
        pixel_x, pixel_y = self.app._geometry().board_to_pixel(7, 7)
        event = SimpleNamespace(x=pixel_x, y=pixel_y)
        self.app._on_mouse_move(event)  # type: ignore[arg-type]
        self.assertEqual(self.app.hover_position, (7, 7))

        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "game_over",
                    "winner": WHITE,
                    "loser": BLACK,
                    "reason": "no_forbidden_free_move",
                },
            )
        )
        self.assertIsNone(self.app.hover_position)
        self.assertEqual(self.app.status_var.get(), "Finished")
        self.assertEqual(self.app.turn_var.get(), "-")
        self.assertEqual(
            label_image_name(self.app.turn_stone_label), str(self.app._stone_images[None])
        )
        self.assertEqual(
            self.app.message_var.get(), "둘 수 있는 자리가 모두 금수여서 패배했습니다."
        )
        self.assertEqual(str(self.app.restart_button["state"]), "normal")
        overlay_items = self.app.canvas.find_withtag("result_overlay")
        self.assertEqual(len(overlay_items), 2)
        overlay_text = next(
            item for item in overlay_items if self.app.canvas.type(item) == "text"
        )
        self.assertEqual(
            self.app.canvas.itemcget(overlay_text, "text"),
            "둘 수 있는 자리가 모두 금수여서 패배했습니다.",
        )

        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "restart",
                    "your_color": WHITE,
                    "starting_color": WHITE,
                    "current_turn": WHITE,
                },
            )
        )
        self.assertEqual(self.app.you_var.get(), WHITE)
        self.assertEqual(self.app.turn_var.get(), WHITE)
        self.assertEqual(
            label_image_name(self.app.you_stone_label), str(self.app._stone_images[WHITE])
        )
        self.assertEqual(
            label_image_name(self.app.turn_stone_label), str(self.app._stone_images[WHITE])
        )
        self.assertEqual(self.app.message_var.get(), "Your turn.")
        self.assertEqual(self.app.canvas.find_withtag("result_overlay"), ())
        self.app._on_mouse_move(event)  # type: ignore[arg-type]
        self.assertEqual(
            self.app.canvas.itemcget(self.app._preview_item_id, "outline"), "#FFFFFF"
        )

    # ------------------------------------------------------------------
    # Renju forbidden points
    # ------------------------------------------------------------------
    def forbidden_state(self, constrained: str | None = BLACK) -> AppState:
        state = AppState(
            view_state=IN_ROOM,
            my_color=BLACK,
            current_turn=BLACK,
            game_status="PLAYING",
            connected=True,
        )
        state.constrained_color = constrained
        state.forbidden_moves = {(3, 4): "DOUBLE_THREE", (9, 6): "OVERLINE"}
        return state

    def board_event(self, x: int, y: int) -> SimpleNamespace:
        pixel_x, pixel_y = self.app._geometry().board_to_pixel(x, y)
        return SimpleNamespace(x=pixel_x, y=pixel_y)

    def test_forbidden_markers_are_drawn_for_the_constrained_player(self) -> None:
        self.app.state = self.forbidden_state()
        self.app._draw_board()
        self.assertEqual(len(self.app.canvas.find_withtag("forbidden_move")), 4)

    def test_forbidden_markers_are_hidden_from_the_other_player(self) -> None:
        self.app.state = self.forbidden_state(constrained=WHITE)
        self.app._draw_board()
        self.assertEqual(self.app.canvas.find_withtag("forbidden_move"), ())

    def test_forbidden_markers_are_hidden_on_an_othello_board(self) -> None:
        state = AppState(
            view_state=IN_ROOM,
            my_color=BLACK,
            current_turn=BLACK,
            game_status="PLAYING",
            connected=True,
            game_type=GameType.OTHELLO,
            board_size=8,
            win_length=None,
        )
        state.constrained_color = BLACK
        state.forbidden_moves = {(3, 4): "DOUBLE_THREE"}
        self.app.state = state
        self.app._draw_board()
        self.assertEqual(self.app.canvas.find_withtag("forbidden_move"), ())

    def test_forbidden_markers_are_hidden_once_the_game_is_finished(self) -> None:
        state = self.forbidden_state()
        state.game_status = "FINISHED"
        self.app.state = state
        self.app._draw_board()
        self.assertEqual(self.app.canvas.find_withtag("forbidden_move"), ())

    def test_hover_preview_skips_forbidden_points(self) -> None:
        self.app.state = self.forbidden_state()
        self.app._draw_board()
        self.app._on_mouse_move(self.board_event(3, 4))  # type: ignore[arg-type]
        self.assertIsNone(self.app.hover_position)
        self.assertIsNone(self.app._preview_item_id)

        self.app._on_mouse_move(self.board_event(5, 5))  # type: ignore[arg-type]
        self.assertEqual(self.app.hover_position, (5, 5))
        self.assertIsNotNone(self.app._preview_item_id)

    def test_clicking_a_forbidden_point_sends_nothing_and_explains_why(self) -> None:
        sent: list[tuple[int, int]] = []
        self.app.network.send_move = lambda x, y: sent.append((x, y))
        self.app.state = self.forbidden_state()
        self.app._draw_board()
        self.app._on_board_click(self.board_event(3, 4))  # type: ignore[arg-type]
        self.assertEqual(sent, [])
        self.assertFalse(self.app._move_pending)
        self.assertEqual(
            self.app.message_var.get(), "3-3 금수 자리입니다. 다른 곳에 두세요."
        )

    def test_server_rejection_highlights_the_point_and_unlocks_input(self) -> None:
        sent: list[tuple[int, int]] = []
        self.app.network.send_move = lambda x, y: sent.append((x, y))
        self.app.state = self.forbidden_state()
        self.app._draw_board()

        # A point the local list does not know about yet: the client is one
        # game_state behind, so the move leaves and the server rejects it.
        self.app._on_board_click(self.board_event(5, 5))  # type: ignore[arg-type]
        self.assertEqual(sent, [(5, 5)])
        self.assertTrue(self.app._move_pending)

        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "error",
                    "code": "FORBIDDEN_MOVE",
                    "forbidden_type": "DOUBLE_FOUR",
                    "x": 5,
                    "y": 5,
                },
            )
        )
        self.assertFalse(self.app._move_pending)
        self.assertEqual(self.app.state.rejected_point, (5, 5))
        self.assertEqual(
            self.app.message_var.get(), "4-4 금수 자리입니다. 다른 곳에 두세요."
        )
        self.assertEqual(len(self.app.canvas.find_withtag("forbidden_rejected")), 1)
        self.assertIsNotNone(self.app._forbidden_flash_after_id)

        self.app._on_board_click(self.board_event(6, 6))  # type: ignore[arg-type]
        self.assertEqual(sent, [(5, 5), (6, 6)])

    def test_rejection_highlight_disappears_after_the_flash(self) -> None:
        self.app.state = self.forbidden_state()
        self.app._handle_network_event(
            NetworkEvent(
                "message",
                payload={
                    "type": "error",
                    "code": "FORBIDDEN_MOVE",
                    "forbidden_type": "OVERLINE",
                    "x": 5,
                    "y": 5,
                },
            )
        )
        self.assertEqual(len(self.app.canvas.find_withtag("forbidden_rejected")), 1)

        self.app._clear_rejected_point()
        self.assertIsNone(self.app.state.rejected_point)
        self.assertIsNone(self.app._forbidden_flash_after_id)
        self.assertEqual(self.app.canvas.find_withtag("forbidden_rejected"), ())


if __name__ == "__main__":
    unittest.main()
