from __future__ import annotations

from dataclasses import dataclass
from math import floor


@dataclass(frozen=True)
class OthelloBoardGeometry:
    board_size: int
    canvas_width: float
    canvas_height: float
    margin: float
    spacing: float
    origin_x: float
    origin_y: float
    stone_radius: float

    @classmethod
    def calculate(
        cls, board_size: int, canvas_width: float, canvas_height: float
    ) -> OthelloBoardGeometry:
        if board_size != 8:
            raise ValueError("Othello board_size must be 8")
        if canvas_width <= 0 or canvas_height <= 0:
            raise ValueError("Canvas dimensions must be positive")
        shortest_side = min(canvas_width, canvas_height)
        margin = min(40.0, max(16.0, shortest_side * 0.04))
        board_pixel_size = max(8.0, shortest_side - margin * 2.0)
        spacing = board_pixel_size / board_size
        origin_x = (canvas_width - board_pixel_size) / 2.0
        origin_y = (canvas_height - board_pixel_size) / 2.0
        return cls(
            board_size=board_size,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            margin=margin,
            spacing=spacing,
            origin_x=origin_x,
            origin_y=origin_y,
            stone_radius=max(4.0, spacing * 0.40),
        )

    @property
    def end_x(self) -> float:
        return self.origin_x + self.spacing * self.board_size

    @property
    def end_y(self) -> float:
        return self.origin_y + self.spacing * self.board_size

    def board_to_pixel(self, x: int, y: int) -> tuple[float, float]:
        if not (0 <= x < self.board_size and 0 <= y < self.board_size):
            raise ValueError("Board coordinate is out of range")
        return (
            self.origin_x + (x + 0.5) * self.spacing,
            self.origin_y + (y + 0.5) * self.spacing,
        )

    def pixel_to_board(self, pixel_x: float, pixel_y: float) -> tuple[int, int] | None:
        if not (
            self.origin_x <= pixel_x < self.end_x
            and self.origin_y <= pixel_y < self.end_y
        ):
            return None
        return (
            floor((pixel_x - self.origin_x) / self.spacing),
            floor((pixel_y - self.origin_y) / self.spacing),
        )
