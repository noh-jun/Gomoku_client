from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class BoardGeometry:
    """One geometry shared by grid, stones, markers, and click conversion."""

    board_size: int
    canvas_width: float
    canvas_height: float
    margin: float
    spacing: float
    origin_x: float
    origin_y: float
    stone_radius: float
    click_threshold: float

    @classmethod
    def calculate(
        cls, board_size: int, canvas_width: float, canvas_height: float
    ) -> BoardGeometry:
        if board_size < 2:
            raise ValueError("board_size must be at least 2")
        if canvas_width <= 0 or canvas_height <= 0:
            raise ValueError("Canvas dimensions must be positive")
        shortest_side = min(canvas_width, canvas_height)
        margin = min(44.0, max(20.0, shortest_side * 0.045))
        drawable_size = max(1.0, shortest_side - margin * 2.0)
        spacing = drawable_size / (board_size - 1)
        board_pixel_size = spacing * (board_size - 1)
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
            stone_radius=max(3.0, spacing * 0.42),
            click_threshold=max(3.0, spacing * 0.45),
        )

    @property
    def end_x(self) -> float:
        return self.origin_x + self.spacing * (self.board_size - 1)

    @property
    def end_y(self) -> float:
        return self.origin_y + self.spacing * (self.board_size - 1)

    def board_to_pixel(self, x: int, y: int) -> tuple[float, float]:
        if not (0 <= x < self.board_size and 0 <= y < self.board_size):
            raise ValueError("Board coordinate is out of range")
        return self.origin_x + x * self.spacing, self.origin_y + y * self.spacing

    def pixel_to_board(self, pixel_x: float, pixel_y: float) -> tuple[int, int] | None:
        x = round((pixel_x - self.origin_x) / self.spacing)
        y = round((pixel_y - self.origin_y) / self.spacing)
        if not (0 <= x < self.board_size and 0 <= y < self.board_size):
            return None
        point_x, point_y = self.board_to_pixel(x, y)
        if hypot(pixel_x - point_x, pixel_y - point_y) > self.click_threshold:
            return None
        return x, y
