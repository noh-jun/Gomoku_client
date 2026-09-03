import unittest

from omok_client.state import AppState, BLACK, WHITE, new_board


class AppStateTests(unittest.TestCase):
    def playing_state(self, board_size: int = 15) -> AppState:
        return AppState(
            my_color=BLACK,
            board_size=board_size,
            current_turn=BLACK,
            game_status="PLAYING",
            connected=True,
        )

    def test_default_and_19_board_creation(self) -> None:
        default_state = AppState()
        large_state = AppState(board_size=19)
        self.assertEqual((len(default_state.board), len(default_state.board[0])), (15, 15))
        self.assertEqual((len(large_state.board), len(large_state.board[0])), (19, 19))

    def test_joined_applies_15_settings(self) -> None:
        state = AppState(board_size=19)
        change = state.apply_server_message(
            {
                "type": "joined",
                "room_id": "room1",
                "your_color": BLACK,
                "board_size": 15,
                "win_length": 5,
            }
        )
        self.assertEqual(state.board_size, 15)
        self.assertEqual(len(state.board), 15)
        self.assertTrue(change.redraw_board)

    def test_joined_applies_19_settings(self) -> None:
        state = AppState()
        state.apply_server_message(
            {
                "type": "joined",
                "room_id": "room2",
                "your_color": WHITE,
                "board_size": 19,
                "win_length": 5,
            }
        )
        self.assertEqual(state.board_size, 19)
        self.assertEqual(state.win_length, 5)
        self.assertTrue(all(len(row) == 19 for row in state.board))

    def test_game_start_can_change_board_size(self) -> None:
        state = AppState()
        change = state.apply_server_message(
            {
                "type": "game_start",
                "board_size": 19,
                "win_length": 5,
                "current_turn": BLACK,
            }
        )
        self.assertEqual(state.board_size, 19)
        self.assertEqual(len(state.board), 19)
        self.assertTrue(change.redraw_board)

    def test_19_board_move_result_updates_edge(self) -> None:
        state = self.playing_state(19)
        change = state.apply_server_message(
            {"type": "move_result", "x": 17, "y": 18, "color": WHITE, "next_turn": BLACK}
        )
        self.assertEqual(state.board[18][17], WHITE)
        self.assertEqual(state.last_move, (17, 18))
        self.assertTrue(change.redraw_board)

    def test_game_state_replaces_size_and_board_atomically(self) -> None:
        state = self.playing_state()
        board = new_board(19)
        board[18][17] = WHITE
        change = state.apply_server_message(
            {
                "type": "game_state",
                "board_size": 19,
                "win_length": 5,
                "board": board,
                "current_turn": BLACK,
                "winner": None,
                "status": "PLAYING",
            }
        )
        self.assertEqual(state.board_size, 19)
        self.assertEqual(state.board[18][17], WHITE)
        self.assertTrue(change.redraw_board)

    def test_game_over_blocks_moves(self) -> None:
        state = self.playing_state()
        state.apply_server_message({"type": "game_over", "winner": BLACK, "reason": "five_in_a_row"})
        self.assertEqual(state.game_status, "GAME_OVER")
        self.assertEqual(state.winner, BLACK)
        self.assertFalse(state.can_move(7, 7))

    def test_restart_preserves_current_board_size(self) -> None:
        state = self.playing_state(19)
        state.board[18][18] = BLACK
        state.game_status = "GAME_OVER"
        state.apply_server_message({"type": "restart", "current_turn": BLACK})
        self.assertEqual(state.board_size, 19)
        self.assertEqual((len(state.board), len(state.board[0])), (19, 19))
        self.assertTrue(all(cell is None for row in state.board for cell in row))
        self.assertEqual(state.game_status, "PLAYING")

    def test_old_server_messages_fall_back_to_15(self) -> None:
        state = AppState()
        state.apply_server_message(
            {"type": "joined", "room_id": "legacy", "your_color": BLACK}
        )
        self.assertEqual(state.board_size, 15)
        self.assertEqual(state.win_length, 5)

    def test_unknown_message_does_not_crash_or_mutate(self) -> None:
        state = self.playing_state()
        before = [row[:] for row in state.board]
        change = state.apply_server_message({"type": "future_message", "value": 1})
        self.assertFalse(change.handled)
        self.assertEqual(state.board, before)

    def test_invalid_game_state_is_atomic(self) -> None:
        state = self.playing_state()
        before = [row[:] for row in state.board]
        with self.assertRaises(ValueError):
            state.apply_server_message(
                {
                    "type": "game_state",
                    "board_size": 19,
                    "win_length": 5,
                    "board": new_board(15),
                    "current_turn": WHITE,
                    "winner": None,
                    "status": "PLAYING",
                }
            )
        self.assertEqual(state.board_size, 15)
        self.assertEqual(state.board, before)
        self.assertEqual(state.current_turn, BLACK)

    def test_rejects_unsafe_board_settings(self) -> None:
        state = AppState()
        with self.assertRaises(ValueError):
            state.apply_server_message(
                {"type": "joined", "room_id": "bad", "your_color": BLACK, "board_size": 500}
            )
        self.assertEqual(state.board_size, 15)


if __name__ == "__main__":
    unittest.main()
