"""오목 앱 아이콘 PNG 생성기.

외부 라이브러리 없이 표준 라이브러리(zlib, struct)만으로 512x512 PNG를 만든다.
Pillow 같은 의존성을 requirements.txt에 추가하지 않기 위한 선택이다.
"""

from __future__ import annotations

import struct
import sys
import zlib

SIZE = 512
MARGIN = 56
GRID_LINES = 5
STONE_RADIUS = 52

WOOD = (222, 184, 135)
BORDER = (250, 246, 238)
LINE = (62, 43, 24)
BLACK_STONE = (25, 25, 25)
WHITE_STONE = (245, 245, 245)


def _draw_stone(pixels, center_x, center_y, radius, fill, edge) -> None:
    for y in range(center_y - radius - 2, center_y + radius + 3):
        for x in range(center_x - radius - 2, center_x + radius + 3):
            if not (0 <= x < SIZE and 0 <= y < SIZE):
                continue
            distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
            if distance <= radius:
                pixels[y][x] = fill
            elif distance <= radius + 2:
                pixels[y][x] = edge


def _build_pixels() -> list[list[tuple[int, int, int]]]:
    pixels = [[WOOD for _ in range(SIZE)] for _ in range(SIZE)]

    for y in range(SIZE):
        for x in range(SIZE):
            if x < MARGIN or x >= SIZE - MARGIN or y < MARGIN or y >= SIZE - MARGIN:
                pixels[y][x] = BORDER

    step = (SIZE - 2 * MARGIN) / (GRID_LINES - 1)
    for index in range(GRID_LINES):
        position = int(MARGIN + index * step)
        for thickness in (-1, 0, 1):
            for along in range(MARGIN, SIZE - MARGIN):
                if 0 <= position + thickness < SIZE:
                    pixels[position + thickness][along] = LINE
                    pixels[along][position + thickness] = LINE

    intersection = lambda index: int(MARGIN + index * step)  # noqa: E731
    _draw_stone(pixels, intersection(2), intersection(2), STONE_RADIUS, BLACK_STONE, LINE)
    _draw_stone(pixels, intersection(1), intersection(1), STONE_RADIUS, WHITE_STONE, LINE)
    _draw_stone(pixels, intersection(3), intersection(3), STONE_RADIUS, WHITE_STONE, LINE)
    _draw_stone(pixels, intersection(1), intersection(3), STONE_RADIUS, BLACK_STONE, LINE)
    return pixels


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def build_png() -> bytes:
    pixels = _build_pixels()
    scanlines = b"".join(
        b"\x00" + b"".join(struct.pack("3B", *pixels[y][x]) for x in range(SIZE))
        for y in range(SIZE)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(scanlines, 9))
        + _chunk(b"IEND", b"")
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("사용법: python make_icon.py <출력 PNG 경로>")
    output_path = sys.argv[1]
    with open(output_path, "wb") as icon_file:
        icon_file.write(build_png())
    print(f"아이콘 생성 완료: {output_path}")


if __name__ == "__main__":
    main()
