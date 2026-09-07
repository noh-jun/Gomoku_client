"""Presentation-only countdown for the server-authoritative Gomoku timer."""

from __future__ import annotations

import math
import time
import tkinter as tk
from collections.abc import Callable


TimerDisplayCallback = Callable[[str, bool], None]


class TurnTimer:
    """Convert a server deadline into text without deciding game state.

    The server remains authoritative for expiration and turn changes. This
    class only schedules Tk callbacks and reports display text to its owner.
    """

    UPDATE_INTERVAL_MS = 100
    WARNING_THRESHOLD_SEC = 5

    def __init__(self, owner: tk.Misc, on_display: TimerDisplayCallback) -> None:
        self._owner = owner
        self._on_display = on_display
        self._after_id: str | None = None
        self._generation = 0
        self._turn_time_limit_sec: int | None = None
        self._turn_revision = 0
        self._remaining_at_sync = 0.0
        self._synced_monotonic = 0.0
        self._mode = "inactive"
        self._last_display: tuple[str, bool] | None = None

    @property
    def turn_revision(self) -> int:
        return self._turn_revision

    def synchronize(
        self,
        turn_time_limit_sec: int | None,
        turn_deadline_unix_ms: int | None,
        turn_revision: int,
    ) -> bool:
        """Apply timer data from an authoritative game-state snapshot.

        Returns ``False`` when the snapshot revision is older than the timer
        already displayed. Network latency is measured once with wall-clock
        time; subsequent countdown updates use the monotonic clock.
        """
        if turn_revision < self._turn_revision:
            return False

        self._cancel_scheduled_update()
        self._turn_revision = turn_revision
        self._turn_time_limit_sec = turn_time_limit_sec

        if turn_deadline_unix_ms is None and turn_time_limit_sec is None:
            self._mode = "infinite"
            self._emit("∞", False)
            return True

        if turn_deadline_unix_ms is None:
            self._mode = "inactive"
            self._emit("--", False)
            return True

        self._mode = "running"
        self._remaining_at_sync = max(
            0.0, turn_deadline_unix_ms / 1000.0 - time.time()
        )
        self._synced_monotonic = time.monotonic()
        generation = self._generation
        self._update(generation)
        return True

    def pause(self) -> None:
        """Show the Undo response wait state until the next game_state."""
        self._cancel_scheduled_update()
        self._mode = "paused"
        self._emit("Paused", False)

    def deactivate(self) -> None:
        """Clear an active countdown for Ready, game-over, or disconnection."""
        self._cancel_scheduled_update()
        self._mode = "inactive"
        self._turn_time_limit_sec = None
        self._remaining_at_sync = 0.0
        self._emit("--", False)

    def close(self) -> None:
        """Cancel the pending Tk callback during application shutdown."""
        self._cancel_scheduled_update()

    def _update(self, generation: int) -> None:
        if generation != self._generation or self._mode != "running":
            return
        elapsed = max(0.0, time.monotonic() - self._synced_monotonic)
        remaining = max(0.0, self._remaining_at_sync - elapsed)
        seconds = int(math.ceil(remaining))
        self._emit(
            f"{seconds // 60:02d}:{seconds % 60:02d}",
            0 < seconds <= self.WARNING_THRESHOLD_SEC,
        )
        if remaining > 0:
            self._after_id = self._owner.after(
                self.UPDATE_INTERVAL_MS,
                lambda: self._update(generation),
            )
        else:
            self._after_id = None

    def _cancel_scheduled_update(self) -> None:
        self._generation += 1
        if self._after_id is not None:
            self._owner.after_cancel(self._after_id)
            self._after_id = None

    def _emit(self, text: str, warning: bool) -> None:
        display = (text, warning)
        if display == self._last_display:
            return
        self._last_display = display
        self._on_display(text, warning)
