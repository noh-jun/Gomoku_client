from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import unittest

from omok_client.gui import OmokApp
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
        self.app = OmokApp(self.root)
        self.app.canvas.configure(width=800, height=700)
        self.root.update_idletasks()

    def tearDown(self) -> None:
        if hasattr(self, "app"):
            self.app._on_close()

    def enter_lobby(self) -> None:
        self.app._handle_network_event(NetworkEvent("connected", message="Connected."))
        self.app.network.request_room_list = lambda: None
        self.app._handle_network_event(NetworkEvent("message", payload={"type": "connected"}))

    def test_connection_lobby_and_game_are_separate_pages(self) -> None:
        self.assertEqual(self.app.connection_frame.winfo_manager(), "grid")
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
        requests: list[str] = []
        self.app.network.create_room = requests.append
        self.app._create_room()
        self.assertTrue(self.app._create_room_modal_open)
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
        self.assertEqual(requests, ["친선 대국"])
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

    def test_hover_and_click_share_coordinates_for_15_and_19(self) -> None:
        for board_size, coordinate, color in (
            (15, (7, 7), BLACK),
            (19, (18, 18), WHITE),
        ):
            with self.subTest(board_size=board_size):
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
                    "reason": "forbidden_move",
                    "forbidden_type": "DOUBLE_THREE",
                },
            )
        )
        self.assertIsNone(self.app.hover_position)
        self.assertEqual(self.app.status_var.get(), "Finished")
        self.assertEqual(self.app.turn_var.get(), "-")
        self.assertEqual(
            label_image_name(self.app.turn_stone_label), str(self.app._stone_images[None])
        )
        self.assertEqual(self.app.message_var.get(), "3-3 금수로 패배했습니다.")
        self.assertEqual(str(self.app.restart_button["state"]), "normal")
        overlay_items = self.app.canvas.find_withtag("result_overlay")
        self.assertEqual(len(overlay_items), 2)
        overlay_text = next(
            item for item in overlay_items if self.app.canvas.type(item) == "text"
        )
        self.assertEqual(
            self.app.canvas.itemcget(overlay_text, "text"), "3-3 금수로 패배했습니다."
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


if __name__ == "__main__":
    unittest.main()
