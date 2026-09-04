from __future__ import annotations

from enum import Enum


class GameType(str, Enum):
    GOMOKU = "GOMOKU"
    OTHELLO = "OTHELLO"

    @property
    def label(self) -> str:
        return "Gomoku" if self is GameType.GOMOKU else "Othello"

    @classmethod
    def from_wire(cls, value: object) -> GameType:
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError("game_type must be GOMOKU or OTHELLO")
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError("game_type must be GOMOKU or OTHELLO") from exc
