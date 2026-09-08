from __future__ import annotations

import json
import unittest

from omok_client.game_type import GameType
from omok_client.gui import INFINITE_TURN_TIME, OmokApp, TURN_TIME_OPTIONS
from omok_client.network import NetworkClient
from omok_client.state import AppState, BLACK, IN_ROOM, WHITE, new_board


def initial_othello_board() -> list[list[str | None]]:
    board = new_board(8)
    board[3][3] = WHITE
    board[3][4] = BLACK
    board[4][3] = BLACK
    board[4][4] = WHITE
    return board


def timeout_capabilities() -> dict[str, object]:
    return {
        "GOMOKU": {
            "turn_time_limits": [None, 5, 10, 15, 30, 60],
            "timeout_action": "SKIP_TURN",
        },
        "OTHELLO": {
            "turn_time_limits": [None, 5, 10, 15, 30, 60],
            "timeout_action": "RANDOM_LEGAL_MOVE",
        },
    }


class FakeVar:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class FakeRadio:
    def __init__(self) -> None:
        self.state = ""

    def configure(self, *, state: str) -> None:
        self.state = state


class OthelloTimeoutStateTests(unittest.TestCase):
    def test_connected_accepts_game_specific_timeout_capabilities(self) -> None:
        state = AppState()

        state.apply_server_message(
            {
                "type": "connected",
                "supported_game_types": ["GOMOKU", "OTHELLO"],
                "room_creation_options": timeout_capabilities(),
            }
        )

        self.assertEqual(
            state.turn_time_limits_for(GameType.OTHELLO),
            (None, 5, 10, 15, 30, 60),
        )

    def test_old_server_keeps_othello_timer_disabled(self) -> None:
        state = AppState()

        state.apply_server_message(
            {
                "type": "connected",
                "supported_game_types": ["GOMOKU", "OTHELLO"],
            }
        )

        self.assertEqual(state.turn_time_limits_for(GameType.OTHELLO), (None,))
        self.assertEqual(
            state.turn_time_limits_for(GameType.GOMOKU),
            (None, 5, 10, 15, 30, 60),
        )

    def test_othello_game_state_accepts_turn_remaining_time(self) -> None:
        state = AppState(
            connected=True,
            view_state=IN_ROOM,
            game_type=GameType.OTHELLO,
            board_size=8,
            win_length=None,
        )
        board = initial_othello_board()

        state.apply_server_message(
            {
                "type": "game_state",
                "game_type": "OTHELLO",
                "board_size": 8,
                "win_length": None,
                "starting_color": BLACK,
                "board": board,
                "current_turn": BLACK,
                "winner": None,
                "loser": None,
                "status": "PLAYING",
                "game_over_reason": None,
                "last_move": None,
                "turn_time_limit_sec": 10,
                "turn_remaining_ms": 9_500,
                "turn_revision": 2,
                "score": {BLACK: 2, WHITE: 2},
                "legal_moves": [
                    {"x": 2, "y": 3},
                    {"x": 3, "y": 2},
                    {"x": 4, "y": 5},
                    {"x": 5, "y": 4},
                ],
            }
        )

        self.assertEqual(state.turn_time_limit_sec, 10)
        self.assertEqual(state.turn_remaining_ms, 9_500)
        self.assertEqual(state.turn_revision, 2)

    def test_timeout_is_informational_until_move_result_arrives(self) -> None:
        board = initial_othello_board()
        state = AppState(
            connected=True,
            view_state=IN_ROOM,
            game_type=GameType.OTHELLO,
            board_size=8,
            win_length=None,
            board=board,
            current_turn=BLACK,
            game_status="PLAYING",
            legal_moves={(2, 3)},
            turn_time_limit_sec=10,
            turn_remaining_ms=1,
        )
        before = [row.copy() for row in state.board]

        change = state.apply_server_message(
            {
                "type": "turn_timeout",
                "game_type": "OTHELLO",
                "timed_out_color": BLACK,
                "current_turn": WHITE,
                "action": "RANDOM_LEGAL_MOVE",
                "move": {"x": 2, "y": 3},
            }
        )

        self.assertEqual(state.board, before)
        self.assertEqual(state.current_turn, WHITE)
        self.assertIsNone(state.turn_remaining_ms)
        self.assertIn("Server auto-move: (2, 3)", change.message)

        state.apply_server_message(
            {
                "type": "move_result",
                "game_type": "OTHELLO",
                "x": 2,
                "y": 3,
                "color": BLACK,
                "next_turn": WHITE,
                "flipped": [{"x": 3, "y": 3, "color": BLACK}],
                "passed_color": None,
            }
        )
        self.assertEqual(state.board[3][2:5], [BLACK, BLACK, BLACK])


class OthelloTimeoutNetworkTests(unittest.TestCase):
    def test_create_room_sends_the_selected_othello_limit(self) -> None:
        client = object.__new__(NetworkClient)
        sent: list[dict[str, object]] = []
        client._submit_send = lambda raw: sent.append(json.loads(raw))  # type: ignore[method-assign]

        client.create_room("Timed Othello", GameType.OTHELLO, 10)

        self.assertEqual(
            sent,
            [
                {
                    "type": "create_room",
                    "room_name": "Timed Othello",
                    "game_type": "OTHELLO",
                    "turn_time_limit_sec": 10,
                }
            ],
        )


class OthelloTimeoutGuiTests(unittest.TestCase):
    def app_for(self, state: AppState) -> OmokApp:
        app = object.__new__(OmokApp)
        app.state = state
        app._create_room_game_type_var = FakeVar(GameType.OTHELLO.value)
        app._create_room_turn_time_var = FakeVar(INFINITE_TURN_TIME)
        app.create_turn_time_radios = [FakeRadio() for _ in TURN_TIME_OPTIONS]
        return app

    def test_advertised_othello_limits_enable_the_timer_choices(self) -> None:
        state = AppState()
        state.apply_server_message(
            {
                "type": "connected",
                "supported_game_types": ["GOMOKU", "OTHELLO"],
                "room_creation_options": timeout_capabilities(),
            }
        )
        app = self.app_for(state)

        app._on_create_room_game_type_changed()

        self.assertTrue(
            all(radio.state == "normal" for radio in app.create_turn_time_radios)
        )

    def test_old_server_only_leaves_infinite_enabled_for_othello(self) -> None:
        state = AppState()
        state.apply_server_message(
            {
                "type": "connected",
                "supported_game_types": ["GOMOKU", "OTHELLO"],
            }
        )
        app = self.app_for(state)

        app._on_create_room_game_type_changed()

        states = [radio.state for radio in app.create_turn_time_radios]
        self.assertEqual(states[:-1], ["disabled"] * (len(states) - 1))
        self.assertEqual(states[-1], "normal")


if __name__ == "__main__":
    unittest.main()
