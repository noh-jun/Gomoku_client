import unittest

from omok_client.game_type import GameType
from omok_client.state import AppState, BLACK, IN_ROOM, LOBBY, WHITE, new_board


def initial_othello_board() -> list[list[str | None]]:
    board = new_board(8)
    board[3][3] = WHITE
    board[3][4] = BLACK
    board[4][3] = BLACK
    board[4][4] = WHITE
    return board


class OthelloStateTests(unittest.TestCase):
    def joined_state(self) -> AppState:
        state = AppState(connected=True, view_state=LOBBY)
        state.apply_server_message(
            {
                "type": "joined",
                "room_id": "room_002",
                "room_name": "친선 오셀로",
                "game_type": "OTHELLO",
                "your_color": BLACK,
                "board_size": 8,
                "win_length": None,
                "starting_color": BLACK,
            }
        )
        return state

    def test_mixed_room_list_and_unknown_type_are_atomic(self) -> None:
        state = AppState(connected=True, view_state=LOBBY)
        state.apply_server_message(
            {
                "type": "room_list",
                "rooms": [
                    {
                        "room_id": "g1",
                        "room_name": "오목방",
                        "game_type": "GOMOKU",
                        "board_size": 15,
                        "win_length": 5,
                        "players": 1,
                        "max_players": 2,
                        "status": "WAITING",
                    },
                    {
                        "room_id": "o1",
                        "room_name": "오셀로방",
                        "game_type": "OTHELLO",
                        "board_size": 8,
                        "win_length": None,
                        "players": 2,
                        "max_players": 2,
                        "status": "PLAYING",
                    },
                ],
            }
        )
        self.assertEqual(
            [room.game_type for room in state.rooms],
            [GameType.GOMOKU, GameType.OTHELLO],
        )
        previous = state.rooms.copy()
        with self.assertRaises(ValueError):
            state.apply_server_message(
                {
                    "type": "room_list",
                    "rooms": [
                        {
                            "room_id": "bad",
                            "room_name": "Bad",
                            "game_type": "CHESS",
                            "board_size": 8,
                            "win_length": None,
                            "players": 1,
                            "max_players": 2,
                            "status": "WAITING",
                        }
                    ],
                }
            )
        self.assertEqual(state.rooms, previous)

    def test_connected_supported_types_are_validated_atomically(self) -> None:
        state = AppState()
        state.apply_server_message(
            {"type": "connected", "supported_game_types": ["GOMOKU", "OTHELLO"]}
        )
        self.assertEqual(
            state.supported_game_types, {GameType.GOMOKU, GameType.OTHELLO}
        )
        previous = state.supported_game_types.copy()
        with self.assertRaises(ValueError):
            state.apply_server_message(
                {"type": "connected", "supported_game_types": ["CHESS"]}
            )
        self.assertEqual(state.supported_game_types, previous)

    def test_room_created_rejects_unknown_game_type(self) -> None:
        state = AppState(connected=True, view_state=LOBBY)
        with self.assertRaises(ValueError):
            state.apply_server_message(
                {
                    "type": "room_created",
                    "room_id": "bad",
                    "room_name": "Bad",
                    "game_type": "CHESS",
                }
            )
        self.assertEqual(state.view_state, LOBBY)

    def test_joined_accepts_othello_and_rejects_wrong_settings(self) -> None:
        state = self.joined_state()
        self.assertEqual(state.game_type, GameType.OTHELLO)
        self.assertEqual(state.board_size, 8)
        self.assertIsNone(state.win_length)
        self.assertEqual(state.starting_color, BLACK)

        with self.assertRaises(ValueError):
            AppState().apply_server_message(
                {
                    "type": "joined",
                    "room_id": "bad",
                    "game_type": "OTHELLO",
                    "your_color": BLACK,
                    "board_size": 10,
                    "win_length": None,
                    "starting_color": BLACK,
                }
            )

    def test_move_result_applies_flips_and_pass_atomically(self) -> None:
        state = self.joined_state()
        state.board = initial_othello_board()
        state.current_turn = BLACK
        state.game_status = "PLAYING"
        state.legal_moves = {(2, 3)}
        change = state.apply_server_message(
            {
                "type": "move_result",
                "game_type": "OTHELLO",
                "x": 2,
                "y": 3,
                "color": BLACK,
                "flipped": [{"x": 3, "y": 3, "color": BLACK}],
                "passed_color": WHITE,
                "next_turn": BLACK,
            }
        )
        self.assertEqual(state.board[3][2:5], [BLACK, BLACK, BLACK])
        self.assertEqual(state.passed_color, WHITE)
        self.assertEqual(state.legal_moves, set())
        self.assertIn("White has no legal move", change.message)

        previous_board = [row.copy() for row in state.board]
        with self.assertRaises(ValueError):
            state.apply_server_message(
                {
                    "type": "move_result",
                    "game_type": "OTHELLO",
                    "x": 2,
                    "y": 2,
                    "color": BLACK,
                    "flipped": [{"x": 99, "y": 3, "color": BLACK}],
                    "passed_color": None,
                    "next_turn": WHITE,
                }
            )
        self.assertEqual(state.board, previous_board)

    def test_game_state_replaces_board_score_and_legal_moves(self) -> None:
        state = self.joined_state()
        board = initial_othello_board()
        state.board[0][0] = BLACK
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
                "score": {BLACK: 2, WHITE: 2},
                "legal_moves": [
                    {"x": 2, "y": 3},
                    {"x": 3, "y": 2},
                    {"x": 4, "y": 5},
                    {"x": 5, "y": 4},
                ],
            }
        )
        self.assertEqual(state.board, board)
        self.assertEqual(state.score, {BLACK: 2, WHITE: 2})
        self.assertEqual(len(state.legal_moves), 4)
        self.assertTrue(state.can_move(2, 3))
        self.assertFalse(state.can_move(0, 0))
        self.assertIsNone(state.constrained_color)
        self.assertEqual(state.forbidden_moves, {})

    def test_game_over_and_restart_use_server_score_and_color(self) -> None:
        state = self.joined_state()
        state.game_status = "PLAYING"
        state.apply_server_message(
            {
                "type": "game_over",
                "game_type": "OTHELLO",
                "winner": BLACK,
                "loser": WHITE,
                "reason": "no_legal_moves",
                "score": {BLACK: 35, WHITE: 29},
            }
        )
        self.assertEqual(state.build_game_over_message(), "You Win\nBlack 35 · White 29")
        self.assertEqual(state.legal_moves, set())

        board = initial_othello_board()
        state.apply_server_message(
            {
                "type": "restart",
                "game_type": "OTHELLO",
                "your_color": WHITE,
                "starting_color": BLACK,
                "current_turn": BLACK,
                "board_size": 8,
                "win_length": None,
                "board": board,
                "score": {BLACK: 2, WHITE: 2},
                "legal_moves": [
                    {"x": 2, "y": 3},
                    {"x": 3, "y": 2},
                    {"x": 4, "y": 5},
                    {"x": 5, "y": 4},
                ],
            }
        )
        self.assertEqual(state.my_color, WHITE)
        self.assertEqual(state.score, {BLACK: 2, WHITE: 2})
        self.assertEqual(state.game_status, "PLAYING")

        state.apply_server_message(
            {
                "type": "game_over",
                "game_type": "OTHELLO",
                "winner": None,
                "loser": None,
                "reason": "no_legal_moves",
                "score": {BLACK: 32, WHITE: 32},
            }
        )
        self.assertEqual(
            state.build_game_over_message(), "Draw\nBlack 32 · White 32"
        )

    def test_disconnect_clears_othello_transient_state(self) -> None:
        state = self.joined_state()
        state.legal_moves = {(2, 3)}
        state.score = {BLACK: 12, WHITE: 8}
        state.passed_color = WHITE
        state.reset_connection()
        self.assertIsNone(state.game_type)
        self.assertEqual(state.legal_moves, set())
        self.assertEqual(state.score, {BLACK: 0, WHITE: 0})
        self.assertIsNone(state.passed_color)


if __name__ == "__main__":
    unittest.main()
