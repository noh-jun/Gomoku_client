from __future__ import annotations

import unicodedata

MAX_ROOM_NAME_LENGTH = 30


def normalize_room_name(value: str) -> str:
    """Return the wire-format room name or raise for invalid user input."""
    if not isinstance(value, str):
        raise ValueError("방 이름은 문자열이어야 합니다.")
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        raise ValueError("방 이름을 입력해 주세요.")
    if len(normalized) > MAX_ROOM_NAME_LENGTH:
        raise ValueError(f"방 이름은 {MAX_ROOM_NAME_LENGTH}자 이하여야 합니다.")
    if any(unicodedata.category(char) in {"Cc", "Cs", "Zl", "Zp"} for char in normalized):
        raise ValueError("방 이름에 제어 문자나 줄바꿈을 사용할 수 없습니다.")
    return normalized
