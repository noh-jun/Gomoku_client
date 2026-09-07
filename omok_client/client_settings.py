from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

DEFAULT_SERVER_URL = "ws://192.168.1.75:8000"
SETTINGS_FILENAME = "client_settings.json"


@dataclass(frozen=True)
class ClientSettings:
    server_url: str = DEFAULT_SERVER_URL
    account_id: str = ""
    password: str = ""
    auto_login: bool = False


def default_settings_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / SETTINGS_FILENAME
    return Path(__file__).resolve().parent.parent / SETTINGS_FILENAME


def normalize_server_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("서버 주소는 문자열이어야 합니다.")
    normalized = value.strip().rstrip("/")
    try:
        parsed = urlsplit(normalized)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("서버 주소의 포트가 올바르지 않습니다.") from exc
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
        raise ValueError("서버 주소는 ws:// 또는 wss://로 시작해야 합니다.")
    if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("서버 주소에는 호스트와 포트만 입력해 주세요.")
    return normalized


def load_client_settings(path: Path | None = None) -> ClientSettings:
    settings_path = path or default_settings_path()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings root must be an object")
        account_id = data.get("account_id", "")
        password = data.get("password", "")
        auto_login = data.get("auto_login", False)
        if not isinstance(account_id, str):
            account_id = ""
        if not isinstance(password, str):
            password = ""
        if not isinstance(auto_login, bool):
            auto_login = False
        return ClientSettings(
            server_url=normalize_server_url(data.get("server_url")),
            account_id=account_id,
            password=password,
            auto_login=auto_login,
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return ClientSettings()


def save_client_settings(settings: ClientSettings, path: Path | None = None) -> None:
    settings_path = path or default_settings_path()
    server_url = normalize_server_url(settings.server_url)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = settings_path.with_name(f"{settings_path.name}.tmp")
    temporary_path.write_text(
        json.dumps(
            {
                "server_url": server_url,
                "account_id": settings.account_id,
                "password": settings.password if settings.auto_login else "",
                "auto_login": settings.auto_login,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(settings_path)
