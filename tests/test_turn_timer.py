from __future__ import annotations

import unittest
from unittest.mock import patch

from omok_client.state import AppState, BLACK, IN_ROOM, new_board
from omok_client.turn_timer import TurnTimer


class FakeOwner:
    def __init__(self) -> None:
        self.callback = None
        self.cancelled: list[str] = []

    def after(self, _delay_ms: int, callback):
        self.callback = callback
        return "timer-1"

    def after_cancel(self, after_id: str) -> None:
        self.cancelled.append(after_id)
        self.callback = None

    def run_callback(self) -> None:
        callback = self.callback
        self.callback = None
        if callback is not None:
            callback()


class TurnTimerTests(unittest.TestCase):
    def test_game_state_accepts_server_remaining_duration(self) -> None:
        state = AppState(
            view_state=IN_ROOM,
            connected=True,
            current_turn=BLACK,
            game_status="PLAYING",
        )

        state.apply_server_message(
            {
                "type": "game_state",
                "game_type": "GOMOKU",
                "board_size": 15,
                "win_length": 5,
                "board": new_board(15),
                "current_turn": BLACK,
                "winner": None,
                "loser": None,
                "status": "PLAYING",
                "game_over_reason": None,
                "last_move": None,
                "turn_time_limit_sec": 30,
                "turn_remaining_ms": 27_500,
                "turn_revision": 4,
                "constrained_color": "WHITE",
                "forbidden_moves": [],
            }
        )

        self.assertEqual(state.turn_remaining_ms, 27_500)
        self.assertEqual(state.turn_revision, 4)

    def test_remaining_duration_uses_monotonic_elapsed_time(self) -> None:
        now = [100.0]
        owner = FakeOwner()
        displays: list[tuple[str, bool]] = []
        timer = TurnTimer(owner, lambda text, warning: displays.append((text, warning)))

        with patch("omok_client.turn_timer.time.monotonic", side_effect=lambda: now[0]):
            self.assertTrue(timer.synchronize(30, 30_000, 1))
            self.assertEqual(displays[-1], ("00:30", False))

            now[0] = 103.2
            owner.run_callback()
            self.assertEqual(displays[-1], ("00:27", False))

    def test_old_or_rewinding_snapshot_does_not_extend_timer(self) -> None:
        now = [100.0]
        owner = FakeOwner()
        displays: list[tuple[str, bool]] = []
        timer = TurnTimer(owner, lambda text, warning: displays.append((text, warning)))

        with patch("omok_client.turn_timer.time.monotonic", side_effect=lambda: now[0]):
            self.assertTrue(timer.synchronize(30, 30_000, 4))
            now[0] = 105.0
            self.assertFalse(timer.synchronize(30, 29_000, 4))
            self.assertFalse(timer.synchronize(30, 10_000, 3))

            owner.run_callback()
            self.assertEqual(displays[-1], ("00:25", False))


if __name__ == "__main__":
    unittest.main()
