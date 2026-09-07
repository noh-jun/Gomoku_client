from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .game_type import GameType
from .room_name import normalize_room_name

DEFAULT_BOARD_SIZE = 15
DEFAULT_WIN_LENGTH = 5
OTHELLO_BOARD_SIZE = 8
MIN_BOARD_SIZE = 5
MAX_BOARD_SIZE = 50
MIN_WIN_LENGTH = 3
EMPTY = None
BLACK = "BLACK"
WHITE = "WHITE"
VALID_COLORS = {BLACK, WHITE}
DISCONNECTED = "DISCONNECTED"
LOBBY = "LOBBY"
IN_ROOM = "IN_ROOM"
PLAYER = "PLAYER"
OBSERVER = "OBSERVER"
VALID_ROLES = {PLAYER, OBSERVER}
FORBIDDEN_LABELS = {
    "DOUBLE_THREE": "3-3 금수",
    "DOUBLE_FOUR": "4-4 금수",
    "OVERLINE": "장목 금수",
}
FORBIDDEN_TYPES = frozenset(FORBIDDEN_LABELS)
SUPPORTED_TURN_TIME_LIMITS = frozenset({5, 10, 15, 30, 60})


def new_board(board_size: int = DEFAULT_BOARD_SIZE) -> list[list[str | None]]:
    _validate_board_size(board_size)
    return [[EMPTY for _ in range(board_size)] for _ in range(board_size)]


def new_score() -> dict[str, int]:
    return {BLACK: 0, WHITE: 0}


@dataclass(frozen=True)
class StateChange:
    handled: bool
    message: str
    redraw_board: bool = False


@dataclass(frozen=True)
class RoomSummary:
    room_id: str
    room_name: str
    game_type: GameType
    board_size: int
    win_length: int | None
    players: int
    max_players: int
    player_count: int
    max_game_players: int
    observer_count: int
    turn_time_limit_sec: int | None
    status: str

    @property
    def can_join(self) -> bool:
        return self.players < self.max_players


@dataclass
class AppState:
    view_state: str = DISCONNECTED
    room_id: str | None = None
    room_name: str | None = None
    rooms: list[RoomSummary] = field(default_factory=list)
    game_type: GameType | None = None
    supported_game_types: set[GameType] = field(
        default_factory=lambda: {GameType.GOMOKU}
    )
    my_color: str | None = None
    my_role: str | None = None
    player_count: int = 0
    observer_count: int = 0
    starting_color: str | None = None
    board_size: int = DEFAULT_BOARD_SIZE
    win_length: int | None = DEFAULT_WIN_LENGTH
    board: list[list[str | None]] = field(default_factory=list)
    current_turn: str | None = None
    game_status: str = "DISCONNECTED"
    winner: str | None = None
    loser: str | None = None
    game_over_reason: str | None = None
    constrained_color: str | None = None
    forbidden_moves: dict[tuple[int, int], str] = field(default_factory=dict)
    rejected_point: tuple[int, int] | None = None
    connected: bool = False
    last_move: tuple[int, int] | None = None
    legal_moves: set[tuple[int, int]] = field(default_factory=set)
    score: dict[str, int] = field(default_factory=new_score)
    passed_color: str | None = None
    ready_colors: set[str] = field(default_factory=set)
    turn_time_limit_sec: int | None = None
    turn_deadline_unix_ms: int | None = None
    turn_revision: int = 0

    def __post_init__(self) -> None:
        effective_type = self.game_type or GameType.GOMOKU
        _validate_game_settings(effective_type, self.board_size, self.win_length)
        self.board = (
            _validated_board(self.board, self.board_size)
            if self.board
            else new_board(self.board_size)
        )
        self.score = _validated_score(self.score)
        self.legal_moves = set(self.legal_moves)
        self.forbidden_moves = dict(self.forbidden_moves)
        self.ready_colors = set(self.ready_colors)

    def apply_board_settings(
        self,
        board_size: int,
        win_length: int | None,
        game_type: GameType | None = None,
    ) -> bool:
        effective_type = game_type or self.game_type or GameType.GOMOKU
        _validate_game_settings(effective_type, board_size, win_length)
        size_changed = board_size != self.board_size
        self.board_size = board_size
        self.win_length = win_length
        self.game_type = effective_type
        if size_changed:
            self.board = new_board(board_size)
            self.last_move = None
        return size_changed

    def reset_room_state(self) -> None:
        self.view_state = LOBBY if self.connected else DISCONNECTED
        self.room_id = None
        self.room_name = None
        self.game_type = None
        self.my_color = None
        self.my_role = None
        self.player_count = 0
        self.observer_count = 0
        self.starting_color = None
        self.board_size = DEFAULT_BOARD_SIZE
        self.win_length = DEFAULT_WIN_LENGTH
        self.board = new_board(self.board_size)
        self.current_turn = None
        self.game_status = LOBBY if self.connected else DISCONNECTED
        self.winner = None
        self.loser = None
        self.game_over_reason = None
        self.constrained_color = None
        self.forbidden_moves.clear()
        self.rejected_point = None
        self.last_move = None
        self.legal_moves.clear()
        self.score = new_score()
        self.passed_color = None
        self.ready_colors.clear()
        self.turn_time_limit_sec = None
        self.turn_deadline_unix_ms = None
        self.turn_revision = 0

    def reset_connection(self) -> None:
        self.connected = False
        self.rooms = []
        self.supported_game_types = {GameType.GOMOKU}
        self.reset_room_state()

    def can_move(self, x: int, y: int) -> bool:
        common = (
            self.connected
            and self.view_state == IN_ROOM
            and self.game_status == "PLAYING"
            and self.my_color is not None
            and self.current_turn == self.my_color
            and 0 <= x < self.board_size
            and 0 <= y < self.board_size
            and self.board[y][x] is EMPTY
        )
        if not common:
            return False
        if self.game_type is GameType.OTHELLO:
            return (x, y) in self.legal_moves
        return not self.is_forbidden_for_me(x, y)

    def is_forbidden_for_me(self, x: int, y: int) -> bool:
        """True only when the point is forbidden for the color I play."""
        return (
            self.my_color is not None
            and self.my_color == self.constrained_color
            and (x, y) in self.forbidden_moves
        )

    def forbidden_label_at(self, x: int, y: int) -> str | None:
        kind = self.forbidden_moves.get((x, y))
        return FORBIDDEN_LABELS.get(kind, "금수") if kind else None

    @property
    def is_finished(self) -> bool:
        return self.game_status in {"FINISHED", "GAME_OVER"}

    @property
    def has_accepted_move(self) -> bool:
        return any(cell is not EMPTY for row in self.board for cell in row)

    @property
    def my_ready(self) -> bool:
        return self.my_color is not None and self.my_color in self.ready_colors

    @property
    def opponent_ready(self) -> bool:
        opponent = WHITE if self.my_color == BLACK else BLACK
        return self.my_color is not None and opponent in self.ready_colors

    def apply_server_message(self, data: dict[str, Any]) -> StateChange:
        message_type = data.get("type")

        if message_type == "connected":
            supported = _validated_supported_game_types(data.get("supported_game_types"))
            self.connected = True
            self.supported_game_types = supported
            self.reset_room_state()
            return StateChange(True, "Lobby connected.")

        if message_type == "room_list":
            rooms = _validated_rooms(data.get("rooms"))
            self.rooms = rooms
            return StateChange(True, f"Room list updated ({len(rooms)}).")

        if message_type == "room_created":
            room_id = _required_room_id(data, "room_created")
            room_name = _room_name_from_message(data, room_id)
            _message_game_type(data, None)
            return StateChange(
                True, f"Room {room_name} created. Waiting for join confirmation..."
            )

        if message_type == "joined":
            game_type = _message_game_type(data, None)
            room_id = _required_room_id(data, "joined")
            room_name = _room_name_from_message(data, room_id)
            role = _required_role(data, "your_role")
            color = _optional_color(data, "your_color", None)
            if role == OBSERVER and color is not None:
                raise ValueError("An observer must have null your_color")
            if role == PLAYER and color is None:
                raise ValueError("A player must have BLACK or WHITE your_color")
            board_size, win_length = _settings_from_message(
                data, game_type, DEFAULT_BOARD_SIZE, DEFAULT_WIN_LENGTH
            )
            starting_color = _validated_starting_color(
                game_type, data, self.starting_color
            )
            turn_time_limit_sec = _turn_time_limit_from_message(
                data, game_type, None
            )
            self.room_id = room_id
            self.room_name = room_name
            self.game_type = game_type
            self.view_state = IN_ROOM
            self.my_color = color
            self.my_role = role
            self.starting_color = starting_color
            self.board_size = board_size
            self.win_length = win_length
            self.board = new_board(board_size)
            self.last_move = None
            self.legal_moves.clear()
            self.score = new_score()
            self.passed_color = None
            self.ready_colors.clear()
            self.turn_time_limit_sec = turn_time_limit_sec
            self.turn_deadline_unix_ms = None
            self.turn_revision = 0
            self.game_status = "WAITING"
            return StateChange(True, "Joined as observer.", True)

        if message_type == "left_room":
            room_id = data.get("room_id")
            if room_id is not None and not isinstance(room_id, str):
                raise ValueError("left_room.room_id must be a string or null")
            self.reset_room_state()
            return StateChange(True, "Returned to lobby.", True)

        if message_type == "player_joined":
            color = _required_color(data, "color")
            return StateChange(
                True, f"{color.title()} player joined. Waiting for game start..."
            )

        if message_type == "role_changed":
            role = _required_role(data, "your_role")
            color = _optional_color(data, "your_color", None)
            if role == PLAYER and color is None:
                raise ValueError("A player must have BLACK or WHITE your_color")
            if role == OBSERVER and color is not None:
                raise ValueError("An observer must have null your_color")
            self.my_role = role
            self.my_color = color
            if role == OBSERVER:
                self.ready_colors.clear()
            return StateChange(True, f"Role changed to {role.title()}.", True)

        if message_type == "room_members":
            player_count = _required_count(data, "player_count", 2)
            observer_count = _required_count(data, "observer_count", 99)
            member_count = _required_count(data, "member_count", 99)
            if player_count + observer_count != member_count:
                raise ValueError("room_members counts do not add up")
            ready = data.get("ready_colors")
            if not isinstance(ready, list) or any(color not in VALID_COLORS for color in ready):
                raise ValueError("room_members.ready_colors must contain valid colors")
            if len(set(ready)) != len(ready) or len(ready) > player_count:
                raise ValueError("room_members.ready_colors is invalid")
            self.player_count = player_count
            self.observer_count = observer_count
            self.ready_colors = set(ready)
            return StateChange(True, f"Room members updated ({member_count}/99).")

        if message_type == "ready_confirmed":
            if data.get("ready") is not True:
                raise ValueError("ready_confirmed.ready must be true")
            if self.my_role != PLAYER or self.my_color is None:
                raise ValueError("Only a player can be confirmed ready")
            self.ready_colors.add(self.my_color)
            return StateChange(True, "Ready confirmed. Waiting for the other player.")

        if message_type == "player_ready":
            color = _required_color(data, "color")
            ready_count = data.get("ready_count")
            required = data.get("required")
            if isinstance(ready_count, bool) or not isinstance(ready_count, int):
                raise ValueError("player_ready.ready_count must be an integer")
            if isinstance(required, bool) or not isinstance(required, int):
                raise ValueError("player_ready.required must be an integer")
            if required != 2 or not 1 <= ready_count <= required:
                raise ValueError("player_ready progress is invalid")
            self.ready_colors.add(color)
            return StateChange(
                True, f"{color.title()} is ready ({ready_count}/{required})."
            )

        if message_type == "game_start":
            game_type = _message_game_type(data, self.game_type)
            current_turn = _required_color(data, "current_turn")
            role = _required_role(data, "your_role")
            my_color = _optional_color(data, "your_color", None)
            if role == PLAYER and my_color is None:
                raise ValueError("A player must have BLACK or WHITE your_color")
            if role == OBSERVER and my_color is not None:
                raise ValueError("An observer must have null your_color")
            board_size, win_length = _settings_from_message(
                data, game_type, self.board_size, self.win_length
            )
            starting_color = _validated_starting_color(
                game_type, data, current_turn
            )
            turn_time_limit_sec = _turn_time_limit_from_message(
                data, game_type, self.turn_time_limit_sec
            )
            board = (
                _validated_board(data["board"], board_size)
                if "board" in data
                else new_board(board_size)
            )
            score = (
                _validated_score(data["score"])
                if "score" in data
                else new_score()
            )
            legal_moves = (
                _validated_legal_moves(data["legal_moves"], board_size, board)
                if "legal_moves" in data
                else set()
            )
            self.game_type = game_type
            self.board_size = board_size
            self.win_length = win_length
            self.board = board
            self.last_move = None
            self.current_turn = current_turn
            self.my_color = my_color
            self.my_role = role
            self.starting_color = starting_color
            self.game_status = "PLAYING"
            self.winner = None
            self.loser = None
            self.game_over_reason = None
            self.constrained_color = None
            self.forbidden_moves.clear()
            self.rejected_point = None
            self.legal_moves = legal_moves
            self.score = score
            self.passed_color = None
            self.ready_colors.clear()
            self.turn_time_limit_sec = turn_time_limit_sec
            self.turn_deadline_unix_ms = None
            return StateChange(True, self.turn_message(), True)

        if message_type == "move_result":
            game_type = _message_game_type(data, self.game_type)
            if self.game_type is not None and game_type is not self.game_type:
                raise ValueError("move_result.game_type does not match current room")
            x = _required_coordinate(data, "x", self.board_size)
            y = _required_coordinate(data, "y", self.board_size)
            color = _required_color(data, "color")
            next_turn = _optional_color(data, "next_turn", None)
            passed_color = _optional_color(data, "passed_color", None)
            flipped = (
                _validated_flipped(data.get("flipped"), self.board_size)
                if game_type is GameType.OTHELLO
                else []
            )
            board = [row.copy() for row in self.board]
            board[y][x] = color
            for flip_x, flip_y, flip_color in flipped:
                board[flip_y][flip_x] = flip_color
            self.board = board
            self.last_move = (x, y)
            self.passed_color = passed_color
            self.current_turn = next_turn
            self.rejected_point = None
            self.legal_moves.clear()
            return StateChange(True, self.turn_message(), True)

        if message_type == "game_over":
            game_type = _message_game_type(data, self.game_type)
            if self.game_type is not None and game_type is not self.game_type:
                raise ValueError("game_over.game_type does not match current room")
            winner = _validated_winner(data.get("winner"), "game_over")
            loser = _optional_color(data, "loser", None)
            reason = _optional_string(data, "reason")
            score = (
                _validated_score(data.get("score"))
                if game_type is GameType.OTHELLO
                else self.score.copy()
            )
            self.game_type = game_type
            self.winner = winner
            self.loser = loser
            self.game_over_reason = reason
            self.score = score
            self.game_status = "FINISHED"
            self.current_turn = None
            self.turn_deadline_unix_ms = None
            self.legal_moves.clear()
            self.forbidden_moves.clear()
            self.rejected_point = None
            self.passed_color = None
            return StateChange(True, self.build_game_over_message(), True)

        if message_type == "game_state":
            game_type = _message_game_type(data, self.game_type)
            if self.game_type is not None and game_type is not self.game_type:
                raise ValueError("game_state.game_type does not match current room")
            board_size, win_length = _settings_from_message(
                data, game_type, self.board_size, self.win_length
            )
            board = _validated_board(data.get("board"), board_size)
            last_move = _optional_point(data, "last_move", board_size)
            current_turn = _optional_color(data, "current_turn", None)
            status = data.get("status")
            if not isinstance(status, str) or not status:
                raise ValueError("game_state.status must be a non-empty string")
            normalized_status = status.upper()
            if normalized_status == "GAME_OVER":
                normalized_status = "FINISHED"
            winner = _validated_winner(data.get("winner"), "game_state")
            loser = _optional_color(data, "loser", None)
            starting_color = _validated_starting_color(
                game_type, data, self.starting_color
            )
            game_over_reason = _optional_string(data, "game_over_reason")
            turn_time_limit_sec = _turn_time_limit_from_message(
                data, game_type, self.turn_time_limit_sec
            )
            turn_deadline_unix_ms = _optional_non_negative_integer(
                data, "turn_deadline_unix_ms"
            )
            turn_revision = _non_negative_integer(
                data.get("turn_revision", self.turn_revision),
                "game_state.turn_revision",
            )
            if game_type is GameType.OTHELLO and turn_deadline_unix_ms is not None:
                raise ValueError("Othello game_state must not contain a turn deadline")
            if game_type is GameType.OTHELLO:
                score = _validated_score(data.get("score"))
                legal_moves = _validated_legal_moves(
                    data.get("legal_moves"), board_size, board
                )
                constrained_color = None
                forbidden_moves: dict[tuple[int, int], str] = {}
            else:
                score = self.score.copy()
                legal_moves = set()
                constrained_color = _optional_color(data, "constrained_color", None)
                forbidden_moves = _validated_forbidden_moves(
                    data.get("forbidden_moves"), board_size, board
                )
            if normalized_status == "FINISHED":
                current_turn = None
                legal_moves.clear()
                forbidden_moves.clear()
            self.game_type = game_type
            self.board_size = board_size
            self.win_length = win_length
            self.board = board
            self.current_turn = current_turn
            self.starting_color = starting_color
            self.winner = winner
            self.loser = loser
            self.game_over_reason = game_over_reason
            self.game_status = normalized_status
            self.score = score
            self.legal_moves = legal_moves
            self.constrained_color = constrained_color
            self.forbidden_moves = forbidden_moves
            self.last_move = last_move
            self.turn_time_limit_sec = turn_time_limit_sec
            if turn_revision >= self.turn_revision:
                self.turn_deadline_unix_ms = turn_deadline_unix_ms
                self.turn_revision = turn_revision
            if normalized_status != "PLAYING":
                self.turn_deadline_unix_ms = None
            return StateChange(True, self.status_message(), True)

        if message_type == "player_disconnected":
            color = _required_color(data, "color")
            self.current_turn = None
            self.turn_deadline_unix_ms = None
            self.game_status = "WAITING"
            self.winner = None
            self.loser = None
            self.game_over_reason = None
            self.legal_moves.clear()
            self.forbidden_moves.clear()
            self.rejected_point = None
            self.passed_color = None
            self.ready_colors.clear()
            return StateChange(
                True, f"{color.title()} player left. Waiting for opponent..."
            )

        if message_type == "undo_requested":
            game_type = _message_game_type(data, self.game_type)
            if game_type is not GameType.GOMOKU:
                raise ValueError("undo_requested.game_type must be GOMOKU")
            requester_color = _required_color(data, "requester_color")
            undo_count = data.get("undo_count")
            if isinstance(undo_count, bool) or undo_count not in {1, 2}:
                raise ValueError("undo_requested.undo_count must be 1 or 2")
            requester = "You" if requester_color == self.my_color else "Opponent"
            self.turn_deadline_unix_ms = None
            return StateChange(
                True,
                f"{requester} requested undo of {undo_count} move(s).",
            )

        if message_type == "turn_timeout":
            game_type = _message_game_type(data, self.game_type)
            if game_type is not GameType.GOMOKU:
                raise ValueError("turn_timeout.game_type must be GOMOKU")
            if self.game_type is not None and game_type is not self.game_type:
                raise ValueError("turn_timeout.game_type does not match current room")
            timed_out_color = _required_color(data, "timed_out_color")
            current_turn = _required_color(data, "current_turn")
            if current_turn == timed_out_color:
                raise ValueError("turn_timeout must switch to the other color")
            self.current_turn = current_turn
            self.turn_deadline_unix_ms = None
            return StateChange(
                True,
                f"{timed_out_color.title()}'s turn timed out.",
            )

        if message_type == "undo_result":
            game_type = _message_game_type(data, self.game_type)
            if game_type is not GameType.GOMOKU:
                raise ValueError("undo_result.game_type must be GOMOKU")
            accepted = data.get("accepted")
            if not isinstance(accepted, bool):
                raise ValueError("undo_result.accepted must be a boolean")
            _required_color(data, "requester_color")
            _required_color(data, "current_turn")
            undone = data.get("undone")
            if not isinstance(undone, list):
                raise ValueError("undo_result.undone must be a list")
            for index, move in enumerate(undone):
                if not isinstance(move, dict):
                    raise ValueError(f"undo_result.undone[{index}] must be an object")
                _required_coordinate(move, "x", self.board_size)
                _required_coordinate(move, "y", self.board_size)
                _required_color(move, "color")
            if not accepted and undone:
                raise ValueError("A rejected undo_result must have an empty undone list")
            message = (
                "Undo accepted. Synchronizing game state..."
                if accepted
                else "Undo request was rejected."
            )
            return StateChange(True, message)

        if message_type == "error":
            text = data.get("message")
            code = data.get("code")
            detail = text if isinstance(text, str) else "The server reported an error."
            if code == "FORBIDDEN_MOVE":
                label = FORBIDDEN_LABELS.get(
                    _optional_string(data, "forbidden_type") or "", "금수"
                )
                self.rejected_point = _rejected_point(data, self.board_size)
                return StateChange(
                    True, f"{label} 자리입니다. 다른 곳에 두세요.", True
                )
            if isinstance(code, str):
                localized = {
                    "ROOM_FULL": "선택한 방이 가득 찼습니다.",
                    "ROOM_NOT_FOUND": "선택한 방이 더 이상 존재하지 않습니다.",
                    "NOT_IN_ROOM": "현재 입장한 방이 없습니다.",
                    "ALREADY_IN_ROOM": "이미 다른 방에 입장해 있습니다.",
                    "INVALID_ROOM_NAME": "사용할 수 없는 방 이름입니다.",
                    "ROOM_NAME_TAKEN": "이미 사용 중인 방 이름입니다.",
                    "CREATE_ROOM_FAILED": "방을 생성하지 못했습니다.",
                    "INVALID_GAME_TYPE": "지원하지 않는 게임 종류입니다.",
                    "INVALID_MOVE": "둘 수 없는 위치입니다.",
                    "FORBIDDEN_MOVE": "금수 자리입니다.",
                    "NOT_YOUR_TURN": "현재 차례가 아닙니다.",
                    "POSITION_OCCUPIED": "이미 돌이 있는 위치입니다.",
                    "GAME_NOT_STARTED": "아직 게임이 시작되지 않았습니다.",
                    "GAME_ALREADY_FINISHED": "이미 종료된 게임입니다.",
                    "UNDO_NOT_AVAILABLE": "되돌릴 수 있는 착수가 없습니다.",
                    "UNDO_ALREADY_PENDING": "이미 처리 중인 되돌리기 요청이 있습니다.",
                    "UNDO_PENDING": "되돌리기 요청을 처리하는 동안에는 진행할 수 없습니다.",
                    "NOT_UNDO_RESPONDER": "상대방만 되돌리기 요청에 응답할 수 있습니다.",
                    "UNSUPPORTED_GAME_OPERATION": "현재 게임에서는 되돌리기를 지원하지 않습니다.",
                    "READY_NOT_AVAILABLE": "현재는 Ready할 수 없습니다.",
                    "READY_REQUIRES_TWO_PLAYERS": "상대 플레이어가 입장해야 Ready할 수 있습니다.",
                    "PLAYER_REQUIRED": "Player만 사용할 수 있는 기능입니다.",
                    "PLAYER_SLOTS_FULL": "Player 자리가 모두 사용 중입니다.",
                    "ALREADY_PLAYER": "이미 Player 상태입니다.",
                    "ALREADY_OBSERVER": "이미 Observer 상태입니다.",
                    "ROLE_CHANGE_NOT_AVAILABLE": "게임 진행 중에는 역할을 변경할 수 없습니다.",
                    "INVALID_TURN_TIME_LIMIT": "지원하지 않는 착수 제한 시간입니다.",
                    "UNSUPPORTED_GAME_OPTION": "현재 게임에서는 해당 방 설정을 지원하지 않습니다.",
                    "TURN_EXPIRED": "착수 제한 시간이 지나 해당 수가 반영되지 않았습니다.",
                }
                detail = localized.get(code, f"{detail} [{code}]")
            return StateChange(True, detail)

        if message_type == "pong":
            return StateChange(True, "Connected.")

        return StateChange(False, f"Unknown server message: {message_type!r}")

    def turn_message(self) -> str:
        if self.passed_color is not None and self.current_turn is not None:
            return (
                f"{self.passed_color.title()} has no legal move. "
                f"{self.current_turn.title()} moves again."
            )
        if self.current_turn is None:
            return "Waiting for turn information..."
        if self.my_role == OBSERVER:
            return f"Observing. {self.current_turn.title()}'s turn."
        return "Your turn." if self.current_turn == self.my_color else "Opponent's turn."

    def build_game_over_message(self) -> str:
        if self.my_role == OBSERVER:
            if self.winner in VALID_COLORS:
                return f"{self.winner.title()} 승리"
            return "무승부입니다."
        if self.game_type is GameType.OTHELLO:
            if self.winner is None:
                title = "Draw"
            elif self.winner == self.my_color:
                title = "You Win"
            elif self.loser == self.my_color or self.winner in VALID_COLORS:
                title = "You Lose"
            else:
                title = "Game Over"
            return f"{title}\nBlack {self.score[BLACK]} · White {self.score[WHITE]}"
        is_draw = self.game_over_reason == "draw" or (
            self.winner in (None, "DRAW") and self.loser is None
        )
        if is_draw:
            return "무승부입니다."
        if self.game_over_reason == "no_forbidden_free_move":
            if self.loser == self.my_color:
                return "둘 수 있는 자리가 모두 금수여서 패배했습니다."
            if self.winner == self.my_color:
                return "상대가 둘 수 있는 자리가 모두 금수여서 승리했습니다."
            return "둘 수 있는 자리가 모두 금수여서 게임이 종료되었습니다."
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


def _message_game_type(
    data: dict[str, Any], current: GameType | None
) -> GameType:
    if "game_type" not in data:
        return current or GameType.GOMOKU
    return GameType.from_wire(data["game_type"])


def _validated_supported_game_types(value: Any) -> set[GameType]:
    if value is None:
        return {GameType.GOMOKU}
    if not isinstance(value, list) or not value:
        raise ValueError("connected.supported_game_types must be a non-empty list")
    return {GameType.from_wire(item) for item in value}


def _settings_from_message(
    data: dict[str, Any],
    game_type: GameType,
    current_size: int,
    current_win_length: int | None,
) -> tuple[int, int | None]:
    default_size = OTHELLO_BOARD_SIZE if game_type is GameType.OTHELLO else current_size
    default_win = None if game_type is GameType.OTHELLO else current_win_length
    board_size = data.get("board_size", default_size)
    win_length = data.get("win_length", default_win)
    _validate_game_settings(game_type, board_size, win_length)
    return board_size, win_length


def _turn_time_limit_from_message(
    data: dict[str, Any],
    game_type: GameType,
    fallback: int | None,
) -> int | None:
    value = data.get("turn_time_limit_sec", fallback)
    if value is not None and (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value not in SUPPORTED_TURN_TIME_LIMITS
    ):
        raise ValueError("turn_time_limit_sec must be 5, 10, 15, 30, 60, or null")
    if game_type is GameType.OTHELLO and value is not None:
        raise ValueError("OTHELLO does not support a turn timer")
    return value


def _non_negative_integer(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{context} must be a non-negative integer")
    return value


def _optional_non_negative_integer(
    data: dict[str, Any], field_name: str
) -> int | None:
    value = data.get(field_name)
    if value is None:
        return None
    return _non_negative_integer(value, f"game_state.{field_name}")


def _validate_game_settings(
    game_type: GameType, board_size: Any, win_length: Any
) -> None:
    if game_type is GameType.OTHELLO:
        if board_size != OTHELLO_BOARD_SIZE or win_length is not None:
            raise ValueError("OTHELLO requires board_size 8 and win_length null")
        return
    _validate_settings(board_size, win_length)


def _validate_settings(board_size: Any, win_length: Any) -> None:
    _validate_board_size(board_size)
    if (
        isinstance(win_length, bool)
        or not isinstance(win_length, int)
        or not MIN_WIN_LENGTH <= win_length <= board_size
    ):
        raise ValueError(
            f"win_length must be an integer from {MIN_WIN_LENGTH} to board_size"
        )


def _validate_board_size(board_size: Any) -> None:
    if (
        isinstance(board_size, bool)
        or not isinstance(board_size, int)
        or not MIN_BOARD_SIZE <= board_size <= MAX_BOARD_SIZE
    ):
        raise ValueError(
            f"board_size must be an integer from {MIN_BOARD_SIZE} to {MAX_BOARD_SIZE}"
        )


def _validated_starting_color(
    game_type: GameType, data: dict[str, Any], fallback: str | None
) -> str | None:
    value = _optional_color(data, "starting_color", fallback)
    if game_type is GameType.OTHELLO and value != BLACK:
        raise ValueError("OTHELLO starting_color must be BLACK")
    return value


def _required_role(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if value not in VALID_ROLES:
        raise ValueError(f"{field_name} must be PLAYER or OBSERVER")
    return value


def _required_count(data: dict[str, Any], field_name: str, maximum: int) -> int:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"{field_name} must be an integer from 0 to {maximum}")
    return value


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


def _validated_score(value: Any) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != VALID_COLORS:
        raise ValueError("score must contain exactly BLACK and WHITE")
    result: dict[str, int] = {}
    for color in (BLACK, WHITE):
        count = value[color]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("score values must be non-negative integers")
        result[color] = count
    return result


def _validated_legal_moves(
    value: Any, board_size: int, board: list[list[str | None]]
) -> set[tuple[int, int]]:
    if not isinstance(value, list):
        raise ValueError("legal_moves must be a list")
    result: set[tuple[int, int]] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each legal move must be an object")
        coordinate = (
            _required_coordinate(item, "x", board_size),
            _required_coordinate(item, "y", board_size),
        )
        if coordinate in result or board[coordinate[1]][coordinate[0]] is not None:
            raise ValueError("legal_moves must be unique empty cells")
        result.add(coordinate)
    return result


def _optional_point(
    data: dict[str, Any], field_name: str, board_size: int
) -> tuple[int, int] | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object or null")
    return (
        _required_coordinate(value, "x", board_size),
        _required_coordinate(value, "y", board_size),
    )


def _validated_forbidden_moves(
    value: Any, board_size: int, board: list[list[str | None]]
) -> dict[tuple[int, int], str]:
    if value is None:
        return {}
    if not isinstance(value, list):
        raise ValueError("forbidden_moves must be a list")
    points: dict[tuple[int, int], str] = {}
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("forbidden_moves entries must be objects")
        x = _required_coordinate(entry, "x", board_size)
        y = _required_coordinate(entry, "y", board_size)
        kind = entry.get("forbidden_type")
        if kind not in FORBIDDEN_TYPES:
            raise ValueError(f"unknown forbidden_type: {kind!r}")
        if board[y][x] is not EMPTY:
            raise ValueError("forbidden_moves must reference empty points")
        points[(x, y)] = kind
    return points


def _rejected_point(data: dict[str, Any], board_size: int) -> tuple[int, int] | None:
    """Coordinates carried by an error frame; None when absent or unusable."""
    x = data.get("x")
    y = data.get("y")
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int)
        or not isinstance(y, int)
        or not 0 <= x < board_size
        or not 0 <= y < board_size
    ):
        return None
    return (x, y)


def _validated_flipped(value: Any, board_size: int) -> list[tuple[int, int, str]]:
    if not isinstance(value, list):
        raise ValueError("OTHELLO move_result.flipped must be a list")
    result: list[tuple[int, int, str]] = []
    seen: set[tuple[int, int]] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each flipped item must be an object")
        x = _required_coordinate(item, "x", board_size)
        y = _required_coordinate(item, "y", board_size)
        color = _required_color(item, "color")
        if (x, y) in seen:
            raise ValueError("flipped coordinates must be unique")
        seen.add((x, y))
        result.append((x, y, color))
    return result


def _validated_winner(value: Any, context: str) -> str | None:
    if value is not None and value not in VALID_COLORS and value != "DRAW":
        raise ValueError(f"{context}.winner is invalid")
    return value


def _required_room_id(data: dict[str, Any], context: str) -> str:
    room_id = data.get("room_id")
    if not isinstance(room_id, str) or not room_id:
        raise ValueError(f"{context}.room_id must be a non-empty string")
    return room_id


def _validated_rooms(value: Any) -> list[RoomSummary]:
    if not isinstance(value, list):
        raise ValueError("room_list.rooms must be a list")
    rooms: list[RoomSummary] = []
    seen_ids: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Each room must be an object")
        room_id = item.get("room_id")
        room_name = item.get("room_name", room_id)
        if not isinstance(room_id, str) or not room_id or room_id in seen_ids:
            raise ValueError("Room IDs must be non-empty and unique")
        if "room_name" in item:
            room_name = _room_name_from_message(item, room_id)
        elif not isinstance(room_name, str) or not room_name:
            raise ValueError("Room names must be non-empty strings")
        game_type = _message_game_type(item, None)
        default_size = OTHELLO_BOARD_SIZE if game_type is GameType.OTHELLO else DEFAULT_BOARD_SIZE
        default_win = None if game_type is GameType.OTHELLO else DEFAULT_WIN_LENGTH
        board_size, win_length = _settings_from_message(
            item, game_type, default_size, default_win
        )
        turn_time_limit_sec = _turn_time_limit_from_message(item, game_type, None)
        players = item.get("players")
        max_players = item.get("max_players")
        player_count = item.get("player_count", players)
        max_game_players = item.get("max_game_players", 2)
        observer_count = item.get("observers", 0)
        status = item.get("status")
        if (
            isinstance(players, bool)
            or not isinstance(players, int)
            or isinstance(max_players, bool)
            or not isinstance(max_players, int)
            or max_players < 1
            or not 0 <= players <= max_players
        ):
            raise ValueError("Room player counts are invalid")
        if (
            isinstance(player_count, bool)
            or not isinstance(player_count, int)
            or isinstance(max_game_players, bool)
            or not isinstance(max_game_players, int)
            or not 0 <= player_count <= max_game_players
            or isinstance(observer_count, bool)
            or not isinstance(observer_count, int)
            or observer_count < 0
        ):
            raise ValueError("Room role counts are invalid")
        if not isinstance(status, str) or not status:
            raise ValueError("Room status must be a non-empty string")
        seen_ids.add(room_id)
        rooms.append(
            RoomSummary(
                room_id=room_id,
                room_name=room_name,
                game_type=game_type,
                board_size=board_size,
                win_length=win_length,
                players=players,
                max_players=max_players,
                player_count=player_count,
                max_game_players=max_game_players,
                observer_count=observer_count,
                turn_time_limit_sec=turn_time_limit_sec,
                status=status.upper(),
            )
        )
    return rooms


def _room_name_from_message(data: dict[str, Any], fallback: str) -> str:
    if "room_name" not in data:
        return fallback
    value = data["room_name"]
    normalized = normalize_room_name(value)
    if value != normalized:
        raise ValueError("room_name must already be normalized")
    return normalized
