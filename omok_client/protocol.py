from __future__ import annotations

import json
from typing import Any


class ClientProtocolError(ValueError):
    """Raised when a server frame is not a valid JSON object."""


def decode_server_message(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClientProtocolError(f"Invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ClientProtocolError("Server message must be a JSON object.")
    if not isinstance(value.get("type"), str):
        raise ClientProtocolError("Server message must contain a string 'type'.")
    return value


def encode_message(message_type: str, **fields: object) -> str:
    return json.dumps({"type": message_type, **fields}, separators=(",", ":"))
