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
                "starting_color": WHITE,
            }
        )
        self.assertEqual(state.board_size, 19)
        self.assertEqual(state.win_length, 5)
        self.assertEqual(state.starting_color, WHITE)
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

    def test_white_can_start_from_server_state(self) -> None:
        state = AppState(my_color=WHITE)
        state.apply_server_message(
            {
                "type": "game_start",
                "starting_color": WHITE,
                "current_turn": WHITE,
            }
        )
        self.assertEqual(state.starting_color, WHITE)
        self.assertEqual(state.current_turn, WHITE)
        self.assertFalse(state.can_move(7, 7))  # Not connected yet.
        state.connected = True
        self.assertTrue(state.can_move(7, 7))

    def test_19_board_move_result_updates_edge(self) -> None:
        state = self.playing_state(19)
        change = state.apply_server_message(
            {"type": "move_result", "x": 17, "y": 18, "color": WHITE, "next_turn": BLACK}
        )
        self.assertEqual(state.board[18][17], WHITE)
        self.assertEqual(state.last_move, (17, 18))
        self.assertTrue(change.redraw_board)

    def test_final_move_accepts_null_next_turn_and_keeps_stone(self) -> None:
        state = self.playing_state()
        state.apply_server_message(
            {"type": "move_result", "x": 7, "y": 7, "color": BLACK, "next_turn": None}
        )
        self.assertEqual(state.board[7][7], BLACK)
        self.assertIsNone(state.current_turn)

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
        change = state.apply_server_message(
            {
                "type": "game_over",
                "winner": BLACK,
                "loser": WHITE,
                "reason": "five_in_a_row",
            }
        )
        self.assertEqual(state.game_status, "FINISHED")
        self.assertEqual(state.winner, BLACK)
        self.assertEqual(state.loser, WHITE)
        self.assertEqual(change.message, "승리했습니다.")
        self.assertIsNone(state.current_turn)
        self.assertFalse(state.can_move(7, 7))

    def test_normal_loss_and_draw_messages(self) -> None:
        loss = self.playing_state()
        loss_change = loss.apply_server_message(
            {
                "type": "game_over",
                "winner": WHITE,
                "loser": BLACK,
                "reason": "five_in_a_row",
            }
        )
        self.assertEqual(loss_change.message, "패배했습니다.")

        draw = self.playing_state()
        draw_change = draw.apply_server_message(
            {"type": "game_over", "winner": None, "loser": None, "reason": "draw"}
        )
        self.assertEqual(draw_change.message, "무승부입니다.")

    def test_forbidden_move_messages(self) -> None:
        labels = {
            "DOUBLE_THREE": "3-3 금수",
            "DOUBLE_FOUR": "4-4 금수",
            "OVERLINE": "장목 금수",
        }
        for forbidden_type, label in labels.items():
            with self.subTest(forbidden_type=forbidden_type, result="loss"):
                state = self.playing_state()
                change = state.apply_server_message(
                    {
                        "type": "game_over",
                        "winner": WHITE,
                        "loser": BLACK,
                        "reason": "forbidden_move",
                        "forbidden_type": forbidden_type,
                        "x": 7,
                        "y": 7,
                    }
                )
                self.assertEqual(change.message, f"{label}로 패배했습니다.")
            with self.subTest(forbidden_type=forbidden_type, result="win"):
                state = self.playing_state()
                change = state.apply_server_message(
                    {
                        "type": "game_over",
                        "winner": BLACK,
                        "loser": WHITE,
                        "reason": "forbidden_move",
                        "forbidden_type": forbidden_type,
                    }
                )
                self.assertEqual(change.message, f"상대방의 {label}로 승리했습니다.")

    def test_move_eligibility_covers_hover_and_click_conditions(self) -> None:
        state = self.playing_state()
        self.assertTrue(state.can_move(7, 7))
        state.board[7][7] = WHITE
        self.assertFalse(state.can_move(7, 7))
        state.board[7][7] = None
        state.current_turn = WHITE
        self.assertFalse(state.can_move(7, 7))
        state.current_turn = BLACK
        state.connected = False
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

    def test_restart_applies_reassigned_color_and_clears_result(self) -> None:
        state = self.playing_state(19)
        state.apply_server_message(
            {
                "type": "game_over",
                "winner": WHITE,
                "loser": BLACK,
                "reason": "forbidden_move",
                "forbidden_type": "DOUBLE_THREE",
            }
        )
        state.apply_server_message(
            {
                "type": "restart",
                "your_color": WHITE,
                "starting_color": WHITE,
                "current_turn": WHITE,
                "board_size": 19,
                "win_length": 5,
            }
        )
        self.assertEqual(state.my_color, WHITE)
        self.assertEqual(state.starting_color, WHITE)
        self.assertEqual(state.current_turn, WHITE)
        self.assertIsNone(state.winner)
        self.assertIsNone(state.loser)
        self.assertIsNone(state.game_over_reason)
        self.assertIsNone(state.forbidden_type)
        self.assertTrue(state.can_move(18, 18))

    def test_finished_game_state_restores_result(self) -> None:
        state = AppState(my_color=WHITE, connected=True)
        board = new_board(19)
        board[9][9] = WHITE
        change = state.apply_server_message(
            {
                "type": "game_state",
                "board_size": 19,
                "win_length": 5,
                "board": board,
                "starting_color": WHITE,
                "current_turn": None,
                "winner": WHITE,
                "loser": BLACK,
                "status": "FINISHED",
                "game_over_reason": "five_in_a_row",
                "forbidden_type": None,
            }
        )
        self.assertTrue(state.is_finished)
        self.assertIsNone(state.current_turn)
        self.assertEqual(state.starting_color, WHITE)
        self.assertEqual(state.board[9][9], WHITE)
        self.assertEqual(change.message, "승리했습니다.")
        self.assertFalse(state.can_move(8, 8))

    def test_error_does_not_overwrite_finished_result(self) -> None:
        state = self.playing_state()
        state.apply_server_message(
            {"type": "game_over", "winner": BLACK, "loser": WHITE, "reason": "five_in_a_row"}
        )
        state.apply_server_message(
            {
                "type": "error",
                "code": "GAME_ALREADY_FINISHED",
                "message": "The game has already finished.",
            }
        )
        self.assertTrue(state.is_finished)
        self.assertEqual(state.winner, BLACK)

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
