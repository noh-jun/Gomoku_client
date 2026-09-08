"""Client-side chat text validation matching the server contract."""

from __future__ import annotations

import unicodedata

MIN_CHAT_TEXT_LENGTH = 1
MAX_CHAT_TEXT_LENGTH = 200
FORBIDDEN_UNICODE_CATEGORIES = frozenset({"Cc", "Cs", "Zl", "Zp"})


def normalize_chat_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("채팅 내용을 입력해 주세요.")
    normalized = value.strip()
    if not MIN_CHAT_TEXT_LENGTH <= len(normalized) <= MAX_CHAT_TEXT_LENGTH:
        raise ValueError("채팅은 1~200자로 입력해 주세요.")
    if any(
        unicodedata.category(character) in FORBIDDEN_UNICODE_CATEGORIES
        for character in normalized
    ):
        raise ValueError("채팅에는 제어문자나 줄바꿈을 사용할 수 없습니다.")
    return normalized
