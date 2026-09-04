# 렌주 금수 착수 금지 전환 클라이언트 개발 지시서

## 1. 목적과 범위

서버가 렌주 금수(3-3, 4-4, 장목)를 **즉시 패배**가 아니라 **착수 금지**로 처리하도록
바뀐다. 클라이언트는 서버가 보내는 금수 좌표 목록을 받아 보드에 표시하고, 금수 자리로의
착수 시도를 사전에 막고, 서버가 거부를 보내오면 그 자리를 강조한다.

이 문서는
[`server/docs/renju-forbidden-block-server-development-guide.md`](../../server/docs/renju-forbidden-block-server-development-guide.md)
의 클라이언트 측 대응 계약이다. 와이어 계약 문구가 두 문서에서 어긋나면 **서버 문서를
기준으로** 맞춘 뒤 두 문서를 함께 갱신한다.

클라이언트는 금수를 **자체 판정하지 않는다**. 렌주 판정 로직을 클라이언트에 복제하면 서버와
갈라질 수 있고, 이 프로젝트의 authoritative 서버 원칙에도 어긋난다. 화면에 그리는 금수는
언제나 서버가 보낸 목록이다.

이 문서는 코드 변경 지시만 담는다. 실제 적용은 별도 작업으로 수행한다.

## 2. 계약 변경 요약

### 2.1 추가되는 것

| 메시지 | 필드 | 값 |
| --- | --- | --- |
| `game_state` | `constrained_color` | 금수 제약을 받는 색. 자유룰이면 `null`. **오목에만** |
| `game_state` | `forbidden_moves` | `[{"x":3,"y":4,"forbidden_type":"DOUBLE_THREE"}, ...]`. **오목에만** |
| `game_state` | `last_move` | `{"x":7,"y":7}` 또는 `null`. **오목·오셀로 공통** |
| `error` | `code: "FORBIDDEN_MOVE"` | `forbidden_type`, `x`, `y`가 함께 온다 |
| `game_over` | `reason: "no_forbidden_free_move"` | 제약 색의 빈 자리가 전부 금수인 교착 종료 |

### 2.2 사라지는 것

| 메시지 | 필드 | 비고 |
| --- | --- | --- |
| `game_over` | `reason: "forbidden_move"` | 더 이상 발생하지 않는다 |
| `game_over` | `forbidden_type`, `x`, `y` | 위와 함께 제거 |
| `game_state` | `forbidden_type` | `forbidden_moves`로 대체 |

`state.py`의 `_optional_string()`은 키가 없으면 `None`을 돌려주므로, 필드 제거만으로는
파싱이 깨지지 않는다. 하지만 관련 상태 필드와 문구 분기는 함께 정리한다.

### 2.3 달라지는 메시지 순서

오목도 오셀로처럼 **매 착수 후 `game_state`가 뒤따른다**.

```text
합법 착수 → move_result → game_state → [game_over]
금수 착수 → error(FORBIDDEN_MOVE)          (둔 사람에게만)
```

금수 착수 시 상대에게는 아무 프레임도 가지 않는다. 상대 화면은 "상대 차례" 그대로다.

## 3. 회귀 위험: 최근 착수 표시

`state.py:361`(`game_state` 핸들러)이 현재 무조건 `self.last_move = None`을 수행한다.
오목이 매 착수 후 `game_state`를 받게 되면, `move_result`가 방금 설정한 `last_move`가
곧바로 지워져 **최근 착수 사각형 표시가 매 수마다 사라진다**.

서버가 `game_state.last_move`를 함께 보내므로 이 라인을 서버 값으로 교체한다.

```python
            # game_state 핸들러
            self.last_move = _optional_point(data, "last_move")
```

오셀로도 지금 같은 문제를 갖고 있으므로 같은 코드로 함께 해결된다.

```python
def _optional_point(data: dict[str, Any], field_name: str) -> tuple[int, int] | None:
    value = data.get(field_name)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object or null")
    x = _required_coordinate(value, "x", MAX_BOARD_SIZE)
    y = _required_coordinate(value, "y", MAX_BOARD_SIZE)
    return (x, y)
```

> 구버전 서버 호환이 필요하면 `"last_move" in data`일 때만 덮어쓰고, 없으면 기존 값을
> 유지한다. §9(D2) 참조.

## 4. 상태 계층 변경 (`omok_client/state.py`)

### 4.1 `AppState` 필드

```python
    constrained_color: str | None = None
    forbidden_moves: dict[tuple[int, int], str] = field(default_factory=dict)
```

`forbidden_type: str | None`(`state.py:81`) 필드를 **제거**한다. 이 필드는 금수 패배 문구
전용이었고, 그 문구가 없어진다.

`__post_init__`에서 `self.forbidden_moves = dict(self.forbidden_moves)`로 복사한다
(`legal_moves`와 동일한 방어).

### 4.2 초기화 경로

`forbidden_type = None`을 지우던 자리마다 두 필드를 함께 초기화한다.

| 위치 | 처리 |
| --- | --- |
| `reset_room_state()` (`state.py:131`) | `constrained_color = None`, `forbidden_moves.clear()` |
| `game_start` (`state.py:262`) | 동일. `game_start`에는 금수 목록이 없고 직후 `game_state`가 온다 |
| `game_over` (`state.py:310`) | `forbidden_moves.clear()` — 끝난 게임에는 금수 표시가 없다 |
| `player_disconnected` (`state.py:374`) | 동일 |
| `restart` (`state.py:416`) | 동일. 직후 `game_state`가 채운다 |

### 4.3 `game_state` 핸들러

```python
            if game_type is GameType.OTHELLO:
                score = _validated_score(data.get("score"))
                legal_moves = _validated_legal_moves(data.get("legal_moves"), board_size, board)
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
```

`forbidden_type = _optional_string(data, "forbidden_type")` 두 줄(`state.py:300`,
`state.py:339`)을 제거한다.

### 4.4 파서

```python
FORBIDDEN_TYPES = {"DOUBLE_THREE", "DOUBLE_FOUR", "OVERLINE"}


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
```

`_validated_legal_moves`와 같은 강도로 검증한다. 좌표 범위, 중복 없음(딕셔너리라 자동
흡수), 빈 점만 허용까지 확인한다.

### 4.5 `can_move()`

```python
    def can_move(self, x: int, y: int) -> bool:
        common = (... 기존과 동일 ...)
        if not common:
            return False
        if self.game_type is GameType.OTHELLO:
            return (x, y) in self.legal_moves
        return not self.is_forbidden_for_me(x, y)

    def is_forbidden_for_me(self, x: int, y: int) -> bool:
        return (
            self.my_color is not None
            and self.my_color == self.constrained_color
            and (x, y) in self.forbidden_moves
        )

    def forbidden_label_at(self, x: int, y: int) -> str | None:
        kind = self.forbidden_moves.get((x, y))
        return FORBIDDEN_LABELS.get(kind, "금수") if kind else None
```

`can_move()`가 `False`가 되므로 클릭과 호버 프리뷰가 **로컬에서 이미 차단된다**. 서버 거부
처리는 방어선이지 1차 방어가 아니다.

### 4.6 `error` 핸들러

`FORBIDDEN_MOVE`는 다른 오류와 달리 **좌표를 동반**하므로 강조 표시에 쓸 수 있게 상태에
남긴다.

```python
    rejected_point: tuple[int, int] | None = None
```

```python
        if message_type == "error":
            code = data.get("code")
            if code == "FORBIDDEN_MOVE":
                kind = _optional_string(data, "forbidden_type") or ""
                label = FORBIDDEN_LABELS.get(kind, "금수")
                x = data.get("x")
                y = data.get("y")
                self.rejected_point = (
                    (x, y)
                    if isinstance(x, int) and isinstance(y, int)
                    and not isinstance(x, bool) and not isinstance(y, bool)
                    else None
                )
                return StateChange(
                    True, f"{label} 자리입니다. 다른 곳에 두세요.", redraw_board=True
                )
            ...  # 기존 localized 매핑
```

기존 `localized` 매핑에도 방어적으로 한 줄 넣어둔다 (좌표가 빠진 프레임 대비).

```python
                    "FORBIDDEN_MOVE": "금수 자리입니다.",
```

`rejected_point`는 `reset_room_state()`, `game_start`, `move_result`, `restart`,
`game_over`에서 `None`으로 되돌린다.

### 4.7 종료 문구

`build_game_over_message()`(`state.py:478-479`)의 금수 분기를 제거하고 교착 분기를 넣는다.

```python
        if self.game_over_reason == "no_forbidden_free_move":
            if self.loser == self.my_color:
                return "둘 수 있는 자리가 모두 금수여서 패배했습니다."
            if self.winner == self.my_color:
                return "상대가 둘 수 있는 자리가 모두 금수여서 승리했습니다."
            return "둘 수 있는 자리가 모두 금수여서 게임이 종료되었습니다."
```

`FORBIDDEN_LABELS`(`state.py:22-26`)는 그대로 유지한다. 용도가 "패배 사유"에서 "금수 종류
표시"로 바뀔 뿐이고, 마커 툴팁과 거부 안내문이 이 사전을 쓴다.

## 5. 렌더링 (`omok_client/gui.py`)

### 5.1 그리기 순서

`_draw_board()`(`gui.py:1015-1019`)에 한 단계를 추가한다. 금수 마커는 격자 위, 돌 아래다.

```python
        self._draw_grid(geometry)
        self._draw_forbidden_moves(geometry)   # 신규
        self._draw_legal_moves(geometry)
        self._draw_stones(geometry)
        self._draw_result_overlay(geometry)
        self._render_preview(geometry)
```

### 5.2 금수 마커

```python
FORBIDDEN_COLOR = "#C62828"
FORBIDDEN_REJECTED_COLOR = "#FF5252"


    def _draw_forbidden_moves(self, geometry) -> None:
        if isinstance(geometry, OthelloBoardGeometry):
            return
        if self.state.game_status != "PLAYING":
            return
        if self.state.my_color != self.state.constrained_color:
            return
        arm = max(3.0, geometry.spacing * 0.26)
        width = max(2, int(geometry.spacing * 0.06))
        for x, y in self.state.forbidden_moves:
            cx, cy = geometry.board_to_pixel(x, y)
            for sign in (1, -1):
                self.canvas.create_line(
                    cx - arm, cy - arm * sign, cx + arm, cy + arm * sign,
                    fill=FORBIDDEN_COLOR, width=width, tags=("forbidden_move",),
                )
        self._draw_rejected_point(geometry, arm, width)
```

표시 조건:

- **오목 전용.** 오셀로 보드에서는 그리지 않는다.
- **진행 중일 때만.** `PLAYING`이 아니면 그리지 않는다.
- **내가 제약 색일 때만.** 서버는 두 플레이어에게 같은 목록을 보내지만, 상대의 금수를
  띄우면 보드가 지저분해지고 자기 수와 혼동된다. 상대 화면에는 그리지 않는다.

`_move_pending` 중에도 마커는 유지한다. `_draw_legal_moves`가 `_move_pending`일 때 숨기는
것과 다른데, 금수 마커는 "지금 클릭 가능한 곳"이 아니라 "구조적으로 둘 수 없는 곳"이라
깜빡이면 안 되기 때문이다.

### 5.3 거부된 착수 강조

서버가 `FORBIDDEN_MOVE`를 보내오면(로컬 방어를 통과한 예외 상황: 상태가 서버보다 한 수
뒤처졌을 때) 해당 점을 굵고 밝게 그린 뒤 자연히 사라지게 한다.

```python
FORBIDDEN_FLASH_MS = 900


    def _draw_rejected_point(self, geometry, arm: float, width: int) -> None:
        point = self.state.rejected_point
        if point is None:
            return
        cx, cy = geometry.board_to_pixel(*point)
        self.canvas.create_oval(
            cx - arm, cy - arm, cx + arm, cy + arm,
            outline=FORBIDDEN_REJECTED_COLOR, width=width + 1,
            tags=("forbidden_rejected",),
        )
```

`error` 수신 후 `root.after(FORBIDDEN_FLASH_MS, ...)`로 `state.rejected_point`를 `None`으로
되돌리고 다시 그린다. 타이머 id는 `_clear_pending_requests()`에서 취소한다.

### 5.4 클릭 안내

`_on_board_click()`(`gui.py:694-703`)의 `can_move()` 실패 분기에 금수 안내를 **점유 검사
앞**에 넣는다.

```python
            elif self.state.is_forbidden_for_me(x, y):
                label = self.state.forbidden_label_at(x, y) or "금수"
                self.message_var.set(f"{label} 자리입니다. 다른 곳에 두세요.")
            elif self.state.board[y][x] is not None:
                ...
```

### 5.5 호버 프리뷰

`_on_mouse_move()`(`gui.py:709-714`)와 `_render_preview()`(`gui.py:1135`)는 이미
`can_move()`를 통해 판단하므로 **코드 변경 없이** 금수 자리에서 프리뷰가 사라진다.
`test_hover_gui.py`에 회귀 테스트만 추가한다.

### 5.6 `_move_pending`

`gui.py:820-821`이 이미 `error` 수신 시 `_clear_pending_requests()`를 호출하므로 거부
후에도 입력이 잠기지 않는다. **변경 불필요**하되 테스트로 고정한다.

## 6. 상태 표시 문구

| 상황 | 문구 |
| --- | --- |
| 금수 자리 클릭 (로컬 차단) | `"3-3 금수 자리입니다. 다른 곳에 두세요."` |
| 서버 거부 수신 | 동일 문구 + 해당 점 강조 |
| 교착 패배 | `"둘 수 있는 자리가 모두 금수여서 패배했습니다."` |
| 교착 승리 | `"상대가 둘 수 있는 자리가 모두 금수여서 승리했습니다."` |

`FORBIDDEN_LABELS`가 이미 `"3-3 금수"`, `"4-4 금수"`, `"장목 금수"`를 담고 있으므로
`f"{label} 자리입니다."`가 자연스러운 한국어가 된다.

## 7. 테스트 지시

### 7.1 재작성 대상

| 파일 | 대상 | 변경 |
| --- | --- | --- |
| `tests/test_state.py` | `forbidden_move` game_over 문구 테스트 | 삭제 후 `no_forbidden_free_move` 테스트로 대체 |
| `tests/test_state.py` | `game_state`의 `forbidden_type` 단언 | `forbidden_moves` 단언으로 전환 |

### 7.2 신규 테스트 (`tests/test_state.py`)

1. `game_state`가 `forbidden_moves`를 파싱해 `{(x, y): "DOUBLE_THREE"}` 형태로 담는다.
2. `constrained_color`가 반영되고, 자유룰(`null`)이면 `None`이다.
3. 오셀로 `game_state`에 두 필드가 없어도 예외 없이 처리되고 빈 값이 된다.
4. `forbidden_moves`에 범위 밖 좌표, 알 수 없는 `forbidden_type`, 이미 돌이 있는 좌표가
   오면 `ValueError`.
5. `status: "FINISHED"`인 `game_state`는 `forbidden_moves`를 비운다.
6. `can_move()`가 내 색이 `constrained_color`일 때 금수 좌표에 `False`를 돌려준다.
7. `can_move()`가 내 색이 제약 색이 **아닐** 때 같은 좌표에 `True`를 돌려준다.
8. `error(FORBIDDEN_MOVE)`가 한국어 문구와 `rejected_point`를 만든다.
9. `error(FORBIDDEN_MOVE)`에 좌표가 없어도 예외 없이 문구만 나온다.
10. `move_result` / `restart` / `game_over` 수신 시 `rejected_point`가 `None`이 된다.
11. `game_state.last_move`가 상태에 반영되고, 연속된 `move_result` → `game_state`에서
    최근 착수 표시가 유지된다. (§3 회귀 방지)
12. `game_over(no_forbidden_free_move)` 문구가 승/패/관전 각각 올바르다.
13. `reset_room_state()` 후 `forbidden_moves`, `constrained_color`, `rejected_point`가
    모두 초기화된다.

### 7.3 신규 테스트 (`tests/test_gui.py`, `tests/test_hover_gui.py`)

14. 내가 제약 색일 때 금수 좌표 수만큼 `forbidden_move` 태그 아이템이 그려진다.
15. 내가 제약 색이 **아니면** 하나도 그려지지 않는다.
16. 오셀로 방에서는 하나도 그려지지 않는다.
17. `FINISHED` 상태에서는 하나도 그려지지 않는다.
18. 금수 좌표 위에서 호버해도 프리뷰 돌이 생기지 않는다.
19. 금수 좌표를 클릭하면 `network.send_move`가 호출되지 않고 안내 문구가 뜬다.
20. `error(FORBIDDEN_MOVE)` 수신 후 `_move_pending`이 `False`이고 다음 클릭이 동작한다.
21. `forbidden_rejected` 아이템이 강조 시간 후 사라진다.

## 8. 수용 기준

- [ ] 제약 색 플레이어의 화면에 금수 자리가 붉은 ✕로 표시된다.
- [ ] 금수 자리에는 호버 프리뷰가 뜨지 않고 클릭해도 `move`가 전송되지 않는다.
- [ ] 상대(비제약 색) 화면에는 금수 마커가 없다.
- [ ] 오셀로 방에는 금수 마커가 없다.
- [ ] 금수 마커가 서버의 `game_state`마다 정확히 갱신되고, 게임 종료 시 사라진다.
- [ ] 최근 착수 사각형이 매 수마다 지워지지 않는다.
- [ ] 금수 관련 어떤 상황에서도 "패배" 문구가 나오지 않는다 (교착 종료 제외).
- [ ] 서버가 `FORBIDDEN_MOVE`를 보내도 입력이 잠기지 않는다.
- [ ] 클라이언트 어디에도 렌주 판정 로직이 없다.

## 9. 결정 대기 항목

| # | 논점 | 권고안 | 대안 |
| --- | --- | --- | --- |
| D1 | 금수 마커 표시 대상 | 제약 색 플레이어에게만 | 양쪽 모두에게 (상대 것은 흐리게) |
| D2 | 구버전 서버 호환 코드 | 넣지 않는다 (서버·클라이언트 동시 배포) | `forbidden_move` game_over 분기를 1릴리스 유지 |
| D3 | 금수 마커 모양 | 붉은 ✕ | 붉은 반투명 원 / 격자 셀 음영 |
| D4 | 거부 강조 지속 시간 | 900ms 후 자동 소멸 | 다음 착수까지 유지 |
| D5 | 금수 종류 툴팁 | 미제공 (문구로만 안내) | 마커 호버 시 `"4-4 금수"` 툴팁 |

D1을 "양쪽 모두"로 바꾸면 §5.2의 표시 조건과 §7.3의 테스트 15를 함께 수정한다.

## 10. 참고

- 서버 계약: [`server/docs/renju-forbidden-block-server-development-guide.md`](../../server/docs/renju-forbidden-block-server-development-guide.md)
- 기존 렌주 동작 설명: `server/README.md` "게임 규칙 > 오목"
- 유사 선례: 오셀로 `legal_moves` 처리 (`state.py:_validated_legal_moves`,
  `gui.py:_draw_legal_moves`). 금수 마커는 이 구조를 반대 방향(둘 수 **없는** 곳)으로
  적용한 것이다.
