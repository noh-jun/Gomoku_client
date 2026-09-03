from types import SimpleNamespace
import tkinter as tk
import unittest

from omok_client.gui import OmokApp
from omok_client.network import NetworkEvent
from omok_client.state import AppState, BLACK, WHITE


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

    def test_connection_and_game_controls_have_separate_sections(self) -> None:
        connection_section = self.app.connect_button.master
        game_section = self.app.restart_button.master
        self.assertIsNot(connection_section, game_section)
        self.assertEqual(connection_section.cget("text"), "Connection")
        self.assertEqual(game_section.cget("text"), "Game")

    def test_hover_and_click_share_coordinates_for_15_and_19(self) -> None:
        for board_size, coordinate, color in (
            (15, (7, 7), BLACK),
            (19, (18, 18), WHITE),
        ):
            with self.subTest(board_size=board_size):
                self.app.state = AppState(
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
        line_count = sum(
            self.app.canvas.type(item) == "line" for item in self.app.canvas.find_all()
        )
        self.assertEqual(line_count, self.app.state.board_size * 2)

        self.app._handle_network_event(NetworkEvent("disconnected", message="Disconnected."))
        self.assertEqual(self.app.canvas.find_all(), ())

    def test_hover_is_hidden_when_move_is_not_allowed(self) -> None:
        self.app.state = AppState(
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
        self.assertEqual(self.app.message_var.get(), "3-3 금수로 패배했습니다.")
        self.assertEqual(str(self.app.restart_button["state"]), "normal")

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
        self.assertEqual(self.app.message_var.get(), "Your turn.")
        self.app._on_mouse_move(event)  # type: ignore[arg-type]
        self.assertEqual(
            self.app.canvas.itemcget(self.app._preview_item_id, "outline"), "#FFFFFF"
        )


if __name__ == "__main__":
    unittest.main()
