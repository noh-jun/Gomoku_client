from __future__ import annotations

import asyncio
from concurrent.futures import Future
from dataclasses import dataclass
import logging
from queue import Queue
import threading
from typing import Any

import websockets

from .chat import normalize_chat_text
from .game_type import GameType
from .protocol import ClientProtocolError, decode_server_message, encode_message

LOGGER = logging.getLogger(__name__)


def build_websocket_uri(server_url: str) -> str:
    server_url = server_url.strip().rstrip("/")
    if not server_url.startswith(("ws://", "wss://")):
        raise ValueError("Server address must start with ws:// or wss://")
    return f"{server_url}/ws"


@dataclass(frozen=True)
class NetworkEvent:
    kind: str
    payload: dict[str, Any] | None = None
    message: str = ""


class NetworkClient:
    """Owns a dedicated asyncio loop and never touches Tk widgets."""

    def __init__(self, events: Queue[NetworkEvent]) -> None:
        self.events = events
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="omok-network", daemon=True)
        self._thread.start()
        self._session: Future[None] | None = None
        self._websocket: Any = None
        self._closing = False

    def connect(self, server_url: str) -> bool:
        if self._closing or (self._session is not None and not self._session.done()):
            return False
        uri = build_websocket_uri(server_url)
        self._session = asyncio.run_coroutine_threadsafe(self._connection_session(uri), self._loop)
        return True

    def disconnect(self) -> None:
        if self._closing:
            return
        asyncio.run_coroutine_threadsafe(self._close_websocket(), self._loop)

    def send_move(self, x: int, y: int) -> None:
        self._submit_send(encode_message("move", x=x, y=y))

    def request_room_list(self) -> None:
        self._submit_send(encode_message("get_room_list"))

    def create_account(self, account_id: str, password: str, nickname: str) -> None:
        self._submit_send(
            encode_message(
                "create_account",
                account_id=account_id,
                password=password,
                nickname=nickname,
            )
        )

    def login(self, account_id: str, password: str) -> None:
        self._submit_send(
            encode_message("login", account_id=account_id, password=password)
        )

    def create_room(
        self,
        room_name: str,
        game_type: GameType,
        turn_time_limit_sec: int | None = None,
    ) -> None:
        game_type = GameType.from_wire(game_type)
        self._submit_send(
            encode_message(
                "create_room",
                room_name=room_name,
                game_type=game_type.value,
                turn_time_limit_sec=turn_time_limit_sec,
            )
        )

    def join_room(self, room_id: str) -> None:
        self._submit_send(encode_message("join_room", room_id=room_id))

    def leave_room(self) -> None:
        self._submit_send(encode_message("leave_room"))

    def become_player(self) -> None:
        self._submit_send(encode_message("become_player"))

    def become_observer(self) -> None:
        self._submit_send(encode_message("become_observer"))

    def send_ready(self) -> None:
        self._submit_send(encode_message("ready"))

    def request_undo(self) -> None:
        self._submit_send(encode_message("undo_request"))

    def respond_undo(self, accepted: bool) -> None:
        self._submit_send(encode_message("undo_response", accepted=accepted))

    def resign(self) -> None:
        self._submit_send(encode_message("resign"))

    def send_chat(self, text: str) -> None:
        self._submit_send(encode_message("chat", text=normalize_chat_text(text)))

    def ping(self) -> None:
        self._submit_send(encode_message("ping"))

    def shutdown(self, timeout: float = 3.0) -> None:
        if self._closing:
            return
        self._closing = True
        close_future = asyncio.run_coroutine_threadsafe(self._close_websocket(), self._loop)
        try:
            close_future.result(timeout=timeout)
        except Exception as exc:
            LOGGER.debug("WebSocket close during shutdown did not complete cleanly: %s", exc)
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=timeout)
        LOGGER.info("Network client stopped")

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        pending = asyncio.all_tasks(self._loop)
        for task in pending:
            task.cancel()
        if pending:
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self._loop.close()

    async def _connection_session(self, uri: str) -> None:
        self.events.put(NetworkEvent("connecting", message=f"Connecting to {uri}"))
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as websocket:
                self._websocket = websocket
                LOGGER.info("Connected to %s", uri)
                self.events.put(NetworkEvent("connected", message="Connected. Waiting for server..."))
                async for raw in websocket:
                    if not isinstance(raw, str):
                        self.events.put(NetworkEvent("protocol_error", message="Ignored non-text server message."))
                        continue
                    try:
                        payload = decode_server_message(raw)
                    except ClientProtocolError as exc:
                        LOGGER.warning("Invalid server message: %s", exc)
                        self.events.put(NetworkEvent("protocol_error", message=str(exc)))
                        continue
                    LOGGER.info("Received %s", payload.get("type"))
                    self.events.put(NetworkEvent("message", payload=payload))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning("Connection ended: %s", exc)
            self.events.put(NetworkEvent("network_error", message=f"Connection lost: {exc}"))
        finally:
            self._websocket = None
            self.events.put(NetworkEvent("disconnected", message="Disconnected."))
            LOGGER.info("Connection closed")

    async def _send(self, raw: str) -> None:
        websocket = self._websocket
        if websocket is None:
            self.events.put(NetworkEvent("network_error", message="Not connected."))
            return
        try:
            await websocket.send(raw)
            LOGGER.info("Sent WebSocket message")
        except Exception as exc:
            LOGGER.warning("Send failed: %s", exc)
            self.events.put(NetworkEvent("network_error", message=f"Send failed: {exc}"))

    async def _close_websocket(self) -> None:
        websocket = self._websocket
        if websocket is not None:
            await websocket.close()

    def _submit_send(self, raw: str) -> None:
        if self._closing:
            return
        asyncio.run_coroutine_threadsafe(self._send(raw), self._loop)
