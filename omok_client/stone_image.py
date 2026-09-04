from __future__ import annotations

import tkinter as tk

from .state import BLACK, WHITE


def create_stone_photo(
    master: tk.Misc,
    color: str | None,
    size: int = 28,
) -> tk.PhotoImage:
    """Create a small raster stone icon with a transparent background."""
    image = tk.PhotoImage(master=master, width=size, height=size)
    if color not in {BLACK, WHITE}:
        return image

    center = (size - 1) / 2
    radius = size * 0.43
    for y in range(size):
        for x in range(size):
            dx = x - center
            dy = y - center
            distance = (dx * dx + dy * dy) ** 0.5
            if distance > radius:
                continue
            if distance > radius - 1.2:
                pixel = "#080808" if color == BLACK else "#555555"
            else:
                highlight = max(0.0, 1.0 - (((x - size * 0.34) ** 2 + (y - size * 0.30) ** 2) ** 0.5) / radius)
                if color == BLACK:
                    shade = int(24 + highlight * 62)
                else:
                    shade = int(218 + highlight * 37)
                pixel = f"#{shade:02x}{shade:02x}{shade:02x}"
            image.put(pixel, (x, y))
    return image
