"""Client-side nickname normalization matching the server contract."""

from __future__ import annotations

import unicodedata

MIN_NICKNAME_LENGTH = 1
MAX_NICKNAME_LENGTH = 20
FORBIDDEN_UNICODE_CATEGORIES = frozenset({"Cc", "Cs", "Zl", "Zp"})


def normalize_nickname(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("닉네임을 입력해 주세요.")
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not MIN_NICKNAME_LENGTH <= len(normalized) <= MAX_NICKNAME_LENGTH:
        raise ValueError("닉네임은 1~20자로 입력해 주세요.")
    if any(
        unicodedata.category(character) in FORBIDDEN_UNICODE_CATEGORIES
        for character in normalized
    ):
        raise ValueError("닉네임에는 제어문자나 줄바꿈을 사용할 수 없습니다.")
    return normalized
