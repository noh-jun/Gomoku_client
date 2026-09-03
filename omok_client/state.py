from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_BOARD_SIZE = 15
DEFAULT_WIN_LENGTH = 5
MIN_BOARD_SIZE = 5
MAX_BOARD_SIZE = 50
MIN_WIN_LENGTH = 3
EMPTY = None
BLACK = "BLACK"
WHITE = "WHITE"
VALID_COLORS = {BLACK, WHITE}
FORBIDDEN_LABELS = {
    "DOUBLE_THREE": "3-3 금수",
    "DOUBLE_FOUR": "4-4 금수",
    "OVERLINE": "장목 금수",
}


def new_board(board_size: int = DEFAULT_BOARD_SIZE) -> list[list[str | None]]:
    _validate_board_size(board_size)
    return [[EMPTY for _ in range(board_size)] for _ in range(board_size)]


@dataclass(frozen=True)
class StateChange:
    handled: bool
    message: str
    redraw_board: bool = False


@dataclass
class AppState:
    room_id: str | None = None
    my_color: str | None = None
    starting_color: str | None = None
    board_size: int = DEFAULT_BOARD_SIZE
    win_length: int = DEFAULT_WIN_LENGTH
    board: list[list[str | None]] = field(default_factory=list)
    current_turn: str | None = None
    game_status: str = "DISCONNECTED"
    winner: str | None = None
    loser: str | None = None
    game_over_reason: str | None = None
    forbidden_type: str | None = None
    connected: bool = False
    last_move: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        _validate_settings(self.board_size, self.win_length)
        self.board = (
            _validated_board(self.board, self.board_size)
            if self.board
            else new_board(self.board_size)
        )

    def apply_board_settings(self, board_size: int, win_length: int) -> bool:
        """Apply server settings and reset the cache only when size changes."""
        _validate_settings(board_size, win_length)
        size_changed = board_size != self.board_size
        self.board_size = board_size
        self.win_length = win_length
        if size_changed:
            self.board = new_board(board_size)
            self.last_move = None
        return size_changed

    def can_move(self, x: int, y: int) -> bool:
        return (
            self.connected
            and self.game_status == "PLAYING"
            and self.my_color is not None
            and self.current_turn == self.my_color
            and 0 <= x < self.board_size
            and 0 <= y < self.board_size
            and self.board[y][x] is EMPTY
        )

    @property
    def is_finished(self) -> bool:
        return self.game_status in {"FINISHED", "GAME_OVER"}

    def apply_server_message(self, data: dict[str, Any]) -> StateChange:
        message_type = data.get("type")

        if message_type == "joined":
            color = _required_color(data, "your_color")
            starting_color = _optional_color(data, "starting_color", self.starting_color)
            room_id = data.get("room_id")
            if not isinstance(room_id, str):
                raise ValueError("joined.room_id must be a string")
            board_size, win_length = _settings_from_message(data, self.board_size, self.win_length)
            self.room_id = room_id
            self.my_color = color
            self.starting_color = starting_color
            self.board_size = board_size
            self.win_length = win_length
            self.board = new_board(board_size)
            self.last_move = None
            self.game_status = "WAITING"
            return StateChange(True, "Waiting for opponent...", True)

        if message_type == "player_joined":
            color = _required_color(data, "color")
            return StateChange(True, f"{color.title()} player joined. Waiting for game start...")

        if message_type == "game_start":
            current_turn = _required_color(data, "current_turn")
            starting_color = _optional_color(data, "starting_color", current_turn)
            board_size, win_length = _settings_from_message(data, self.board_size, self.win_length)
            redraw = self.apply_board_settings(board_size, win_length)
            self.current_turn = current_turn
            self.starting_color = starting_color
            self.game_status = "PLAYING"
            self.winner = None
            self.loser = None
            self.game_over_reason = None
            self.forbidden_type = None
            return StateChange(True, self.turn_message(), redraw)

        if message_type == "move_result":
            x = _required_coordinate(data, "x", self.board_size)
            y = _required_coordinate(data, "y", self.board_size)
            color = _required_color(data, "color")
            next_turn = _optional_color(data, "next_turn", None)
            self.board[y][x] = color
            self.last_move = (x, y)
            self.current_turn = next_turn
            return StateChange(True, self.turn_message(), True)

        if message_type == "game_over":
            winner = data.get("winner")
            if winner is not None and winner not in VALID_COLORS and winner != "DRAW":
                raise ValueError("game_over.winner must be BLACK, WHITE, DRAW, or null")
            loser = _optional_color(data, "loser", None)
            reason = _optional_string(data, "reason")
            forbidden_type = _optional_string(data, "forbidden_type")
            self.winner = winner
            self.loser = loser
            self.game_over_reason = reason
            self.forbidden_type = forbidden_type
            self.game_status = "FINISHED"
            self.current_turn = None
            return StateChange(True, self.build_game_over_message())

        if message_type == "game_state":
            board_size, win_length = _settings_from_message(data, self.board_size, self.win_length)
            board = _validated_board(data.get("board"), board_size)
            current_turn = data.get("current_turn")
            if current_turn is not None and current_turn not in VALID_COLORS:
                raise ValueError("game_state.current_turn is invalid")
            status = data.get("status")
            if not isinstance(status, str):
                raise ValueError("game_state.status must be a string")
            winner = data.get("winner")
            if winner is not None and winner not in VALID_COLORS and winner != "DRAW":
                raise ValueError("game_state.winner is invalid")
            starting_color = _optional_color(data, "starting_color", self.starting_color)
            loser = _optional_color(data, "loser", None)
            game_over_reason = _optional_string(data, "game_over_reason")
            forbidden_type = _optional_string(data, "forbidden_type")
            normalized_status = status.upper()
            if normalized_status == "GAME_OVER":
                normalized_status = "FINISHED"
            self.board_size = board_size
            self.win_length = win_length
            self.board = board
            self.current_turn = current_turn
            self.starting_color = starting_color
            self.winner = winner
            self.loser = loser
            self.game_over_reason = game_over_reason
            self.forbidden_type = forbidden_type
            self.game_status = normalized_status
            if self.is_finished:
                self.current_turn = None
            self.last_move = None
            return StateChange(True, self.status_message(), True)

        if message_type == "player_disconnected":
            color = _required_color(data, "color")
            return StateChange(True, f"{color.title()} player disconnected.")

        if message_type == "restart":
            current_turn = _required_color(data, "current_turn")
            my_color = _optional_color(data, "your_color", self.my_color)
            starting_color = _optional_color(data, "starting_color", current_turn)
            board_size, win_length = _settings_from_message(data, self.board_size, self.win_length)
            self.board_size = board_size
            self.win_length = win_length
            self.board = new_board(board_size)
            self.current_turn = current_turn
            self.my_color = my_color
            self.starting_color = starting_color
            self.winner = None
            self.loser = None
            self.game_over_reason = None
            self.forbidden_type = None
            self.game_status = "PLAYING"
            self.last_move = None
            return StateChange(True, self.turn_message(), True)

        if message_type == "error":
            text = data.get("message")
            code = data.get("code")
            detail = text if isinstance(text, str) else "The server reported an error."
            if isinstance(code, str):
                detail = f"{detail} [{code}]"
            return StateChange(True, detail)

        if message_type == "pong":
            return StateChange(True, "Connected.")

        return StateChange(False, f"Unknown server message: {message_type!r}")

    def turn_message(self) -> str:
        if self.current_turn is None:
            return "Waiting for turn information..."
        return "Your turn." if self.current_turn == self.my_color else "Opponent's turn."

    def build_game_over_message(self) -> str:
        is_draw = self.game_over_reason == "draw" or (
            self.winner in (None, "DRAW") and self.loser is None
        )
        if is_draw:
            return "무승부입니다."
        if self.game_over_reason == "forbidden_move":
            label = FORBIDDEN_LABELS.get(self.forbidden_type or "", "금수")
            if self.loser == self.my_color:
                return f"{label}로 패배했습니다."
            if self.winner == self.my_color:
                return f"상대방의 {label}로 승리했습니다."
            return f"{label}로 게임이 종료되었습니다."
        if self.winner == self.my_color:
            return "승리했습니다."
        if self.loser == self.my_color or (
            self.winner in VALID_COLORS and self.winner != self.my_color
        ):
            return "패배했습니다."
        return "게임이 종료되었습니다."

    def status_message(self) -> str:
        if self.game_status == "PLAYING":
            return self.turn_message()
        if self.is_finished:
            return self.build_game_over_message()
        if self.game_status == "WAITING":
            return "Waiting for opponent..."
        return self.game_status.replace("_", " ").title() + "."


def _settings_from_message(
    data: dict[str, Any], current_size: int, current_win_length: int
) -> tuple[int, int]:
    board_size = data.get("board_size", current_size)
    win_length = data.get("win_length", current_win_length)
    _validate_settings(board_size, win_length)
    return board_size, win_length


def _validate_settings(board_size: Any, win_length: Any) -> None:
    _validate_board_size(board_size)
    if (
        isinstance(win_length, bool)
        or not isinstance(win_length, int)
        or not MIN_WIN_LENGTH <= win_length <= board_size
    ):
        raise ValueError(f"win_length must be an integer from {MIN_WIN_LENGTH} to board_size")


def _validate_board_size(board_size: Any) -> None:
    if (
        isinstance(board_size, bool)
        or not isinstance(board_size, int)
        or not MIN_BOARD_SIZE <= board_size <= MAX_BOARD_SIZE
    ):
        raise ValueError(
            f"board_size must be an integer from {MIN_BOARD_SIZE} to {MAX_BOARD_SIZE}"
        )


def _required_color(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if value not in VALID_COLORS:
        raise ValueError(f"{field_name} must be BLACK or WHITE")
    return value


def _optional_color(
    data: dict[str, Any], field_name: str, fallback: str | None
) -> str | None:
    if field_name not in data:
        return fallback
    value = data[field_name]
    if value is not None and value not in VALID_COLORS:
        raise ValueError(f"{field_name} must be BLACK, WHITE, or null")
    return value


def _optional_string(data: dict[str, Any], field_name: str) -> str | None:
    value = data.get(field_name)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null")
    return value


def _required_coordinate(data: dict[str, Any], field_name: str, board_size: int) -> int:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < board_size:
        raise ValueError(f"{field_name} must be an integer from 0 to {board_size - 1}")
    return value


def _validated_board(value: Any, board_size: int) -> list[list[str | None]]:
    if not isinstance(value, list) or len(value) != board_size:
        raise ValueError(f"game_state.board must contain {board_size} rows")
    result: list[list[str | None]] = []
    for row in value:
        if not isinstance(row, list) or len(row) != board_size:
            raise ValueError(f"Each board row must contain {board_size} cells")
        normalized_row: list[str | None] = []
        for cell in row:
            normalized = None if cell in (None, "", "EMPTY") else cell
            if normalized is not None and normalized not in VALID_COLORS:
                raise ValueError(f"Invalid board cell: {cell!r}")
            normalized_row.append(normalized)
        result.append(normalized_row)
    return result
