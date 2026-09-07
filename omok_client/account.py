"""Client-side account input validation matching the server contract."""

from __future__ import annotations

import re

MIN_ACCOUNT_ID_LENGTH = 4
MAX_ACCOUNT_ID_LENGTH = 20
MIN_PASSWORD_LENGTH = 4
MAX_PASSWORD_LENGTH = 20
_ACCOUNT_ID_PATTERN = re.compile(r"^[A-Za-z]{4,20}$")


def normalize_account_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Account ID must be a string.")
    normalized = value.strip()
    if len(normalized) < MIN_ACCOUNT_ID_LENGTH:
        raise ValueError("Account ID must contain at least 4 letters.")
    if len(normalized) > MAX_ACCOUNT_ID_LENGTH:
        raise ValueError("Account ID must contain at most 20 letters.")
    if not _ACCOUNT_ID_PATTERN.fullmatch(normalized):
        raise ValueError("Account ID may contain English letters only.")
    return normalized.lower()


def validate_password(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Password must be a string.")
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError("Password must contain at least 4 characters.")
    if len(value) > MAX_PASSWORD_LENGTH:
        raise ValueError("Password must contain at most 20 characters.")
    if any(character.isspace() for character in value):
        raise ValueError("Password must not contain whitespace.")
    return value
