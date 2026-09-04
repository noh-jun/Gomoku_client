# 오목·오셀로 클라이언트 개발 지시서

> 후속 변경: 오셀로의 Room별 8/10/12 보드 크기 선택은
> [`othello-board-size-client-development-guide.md`](./othello-board-size-client-development-guide.md)를
> 따른다. 해당 문서가 이 문서의 “Othello는 정확히 8×8” 조건보다 우선한다.

## 1. 목적

현재 Tkinter 오목 클라이언트에 오셀로를 추가한다.

사용자는 Lobby의 Create Room 모달에서 방 이름과 게임 종류를 선택하고, 오셀로인 경우
서버가 허용한 보드 크기도 선택한다. 클라이언트는
게임 규칙이나 승패를 독자적으로 확정하지 않고, 서버가 전달하는 Room 정보와 게임 상태를
검증한 뒤 화면에 반영한다.

지원 게임 종류는 다음 두 값으로 고정한다.

```text
GOMOKU
OTHELLO
```

이번 작업은 기존 Lobby, Room 이름, WebSocket 스레드, 화면 전환 구조를 유지하면서
게임 종류별 상태와 보드 표현을 확장하는 작업이다.

## 2. 핵심 원칙

- Room 식별에는 계속 `room_id`를 사용한다.
- `room_name`은 표시 이름이고 `game_type`은 게임 규칙 선택자다.
- 클라이언트는 오셀로의 뒤집기, pass, 종료, 점수를 자체 판정하지 않는다.
- 클릭 직후 로컬 보드를 변경하지 않는다. 서버 응답 후에만 화면을 변경한다.
- 서버 메시지는 필요한 필드를 모두 검증한 다음 AppState에 원자적으로 반영한다.
- 기존 오목의 15×15/19×19, 렌주 금수, Restart, Hover 동작을 깨뜨리지 않는다.
- 알 수 없는 `game_type`은 임의로 GOMOKU로 처리하지 않고 protocol error로 거부한다.

## 3. 현재 코드에서 변경할 지점

현재 구현은 다음 부분에서 오목을 전제한다.

- `omok_client/state.py`
  - `RoomSummary`와 `AppState`에 게임 종류가 없다.
  - `win_length`가 항상 정수라고 가정한다.
  - `move_result`는 한 칸만 변경한다.
  - `can_move()`는 빈 교차점 여부만 검사한다.
- `omok_client/network.py`
  - `create_room()`이 `room_name`만 전송한다.
- `omok_client/gui.py`
  - Create Room 모달에 게임 선택 UI가 없다.
  - 하나의 오목 교차점 렌더러가 모든 보드를 그린다.
  - 결과 문구가 오목 금수와 현재 승패 표현을 중심으로 구성되어 있다.
- `omok_client/board.py`
  - 좌표가 오목판 교차점 중심으로 계산된다.

전체 GUI나 네트워크 계층을 다시 작성하지 말고 이 결합 지점만 분리한다.

## 4. 서버 WebSocket 계약

클라이언트 개발은 아래 계약을 기준으로 한다. 서버 작업과 필드명이 달라지면 양쪽 문서를
먼저 같은 값으로 맞춘다.

### 4.1 Room 생성

```json
{
  "type": "create_room",
  "room_name": "친선 오셀로",
  "game_type": "OTHELLO",
  "board_size": 8
}
```

`game_type`은 반드시 대문자 wire value를 사용한다. Room ID는 보내지 않는다. 오셀로의
`board_size` 선택 규칙은 후속 보드 크기 지시서를 따른다.

오목 방 예:

```json
{
  "type": "create_room",
  "room_name": "오목 초보방",
  "game_type": "GOMOKU"
}
```

### 4.2 Room 생성 확인

```json
{
  "type": "room_created",
  "room_id": "room_002",
  "room_name": "친선 오셀로",
  "game_type": "OTHELLO"
}
```

`room_created`만으로 Game 화면으로 전환하지 않는다. 기존과 같이 `joined`를 받아야
입장을 확정한다.

### 4.3 Room List

```json
{
  "type": "room_list",
  "rooms": [
    {
      "room_id": "room_001",
      "room_name": "오목 초보방",
      "game_type": "GOMOKU",
      "board_size": 15,
      "win_length": 5,
      "players": 1,
      "max_players": 2,
      "status": "WAITING"
    },
    {
      "room_id": "room_002",
      "room_name": "친선 오셀로",
      "game_type": "OTHELLO",
      "board_size": 8,
      "win_length": null,
      "players": 2,
      "max_players": 2,
      "status": "PLAYING"
    }
  ]
}
```

Room 입장은 계속 불변 ID만 사용한다.

```json
{
  "type": "join_room",
  "room_id": "room_002"
}
```

### 4.4 joined

```json
{
  "type": "joined",
  "room_id": "room_002",
  "room_name": "친선 오셀로",
  "game_type": "OTHELLO",
  "your_color": "BLACK",
  "board_size": 8,
  "win_length": null,
  "starting_color": "BLACK"
}
```

클라이언트는 `joined.game_type`을 현재 Room의 최종 게임 종류로 저장한다. 생성 요청 때
선택했던 로컬 값보다 서버 응답이 우선한다.

### 4.5 오셀로 move_result

```json
{
  "type": "move_result",
  "game_type": "OTHELLO",
  "x": 2,
  "y": 3,
  "color": "BLACK",
  "flipped": [
    {"x": 3, "y": 3, "color": "BLACK"}
  ],
  "passed_color": null,
  "next_turn": "WHITE"
}
```

- `x`, `y`: 새 돌을 놓은 셀
- `flipped`: 서버가 뒤집은 셀 전체
- `passed_color`: 합법 수가 없어 자동 pass된 색, 없으면 `null`
- `next_turn`: 다음 차례, 게임 종료 시 `null`

오목의 기존 `move_result`에는 `flipped`와 `passed_color`가 없어도 된다.

### 4.6 오셀로 game_state

```json
{
  "type": "game_state",
  "game_type": "OTHELLO",
  "board_size": 8,
  "win_length": null,
  "starting_color": "BLACK",
  "board": [
    [null, null, null, null, null, null, null, null]
  ],
  "current_turn": "BLACK",
  "winner": null,
  "loser": null,
  "status": "PLAYING",
  "game_over_reason": null,
  "forbidden_type": null,
  "score": {"BLACK": 2, "WHITE": 2},
  "legal_moves": [
    {"x": 2, "y": 3},
    {"x": 3, "y": 2},
    {"x": 4, "y": 5},
    {"x": 5, "y": 4}
  ]
}
```

실제 `board`는 `board_size`개 행과 각 행 `board_size`개 셀을 가져야 한다. 위 예시는
8×8 Room을 설명하기 위해 행을 축약했다.

`legal_moves`는 `current_turn` 플레이어가 둘 수 있는 서버 계산 좌표다. 클라이언트는
이 목록을 Hover와 클릭 가능 여부에 사용한다.

서버는 오셀로 착수 후 `move_result`에 이어 authoritative `game_state`를 보내는 것을
계약으로 한다. 클라이언트는 `move_result`로 즉시 돌과 뒤집기 표현을 갱신할 수 있지만,
최종 상태는 뒤이어 받은 `game_state`로 교정한다.

### 4.7 game_over

```json
{
  "type": "game_over",
  "game_type": "OTHELLO",
  "winner": "BLACK",
  "loser": "WHITE",
  "reason": "no_legal_moves",
  "score": {"BLACK": 35, "WHITE": 29},
  "message": "BLACK wins 35 to 29."
}
```

동점이면 `winner`와 `loser`는 모두 `null`이다. 클라이언트는 점수로 승패를 다시
판정하지 않고 서버의 결과를 표시한다.

`reason`은 양쪽 모두 합법 수가 없으면 `no_legal_moves`, 64칸이 모두 차면
`board_full`이다.

### 4.8 오류

게임 선택과 관련해 다음 코드를 처리한다.

```text
INVALID_GAME_TYPE
INVALID_MOVE
NOT_YOUR_TURN
POSITION_OCCUPIED
GAME_NOT_STARTED
GAME_ALREADY_FINISHED
```

오셀로에서 뒤집을 돌이 없는 착수는 서버가 `INVALID_MOVE`로 거부하는 계약을 권장한다.
오류를 받으면 보드는 변경하지 않고 pending 상태만 해제한다.

## 5. 데이터 모델 변경

### 5.1 GameType

`omok_client/game_type.py`를 추가한다.

```python
from enum import Enum


class GameType(str, Enum):
    GOMOKU = "GOMOKU"
    OTHELLO = "OTHELLO"
```

wire parsing은 반드시 enum 변환을 거치고 실패하면 `ValueError`를 발생시킨다.

### 5.2 RoomSummary

`state.py`의 RoomSummary를 다음 개념으로 확장한다.

```python
@dataclass(frozen=True)
class RoomSummary:
    room_id: str
    room_name: str
    game_type: GameType
    board_size: int
    win_length: int | None
    players: int
    max_players: int
    status: str
```

`can_join` 정책은 게임 종류와 무관하게 현재의 인원/상태 정책을 유지한다.

### 5.3 AppState

다음 필드를 추가하거나 변경한다.

```python
game_type: GameType | None = None
win_length: int | None = DEFAULT_WIN_LENGTH
legal_moves: set[tuple[int, int]] = field(default_factory=set)
score: dict[str, int] = field(
    default_factory=lambda: {"BLACK": 0, "WHITE": 0}
)
passed_color: str | None = None
```

상태 초기화 경계:

- disconnect/left_room: `game_type`, `legal_moves`, `score`, `passed_color` 초기화
- joined: 서버 설정과 빈 보드를 적용하고 현재 게임 종류 저장
- game_start/restart: 게임별 초기 상태를 서버 메시지로 적용
- player_disconnected: 착수 불가, `legal_moves` 비우기
- game_over: `current_turn=None`, `legal_moves` 비우기, 최종 점수 보존

## 6. 설정 검증 분리

현재 `_settings_from_message()`와 `_validate_settings()`는 `win_length`가 항상 정수라고
가정한다. 다음처럼 게임 종류에 따라 분리한다.

```text
GOMOKU
  board_size: 현재 허용 범위
  win_length: 3..board_size 정수

OTHELLO
  board_size: connected에서 광고한 Room 생성 allowlist의 짝수 크기
  capability가 없는 구버전 서버에서는 8
  win_length: null
  starting_color: BLACK
```

메시지를 적용할 때는 다음 순서를 지킨다.

1. `game_type` 검증
2. 게임별 settings 검증
3. board 전체 크기와 셀 값 검증
4. score, legal_moves, turn, result 검증
5. 모든 검증 성공 후 AppState 변경

중간 필드가 잘못됐다고 기존의 정상 상태 일부를 먼저 변경하면 안 된다.

## 7. NetworkClient 변경

`network.py`의 create_room signature를 확장한다.

```python
def create_room(self, room_name: str, game_type: GameType) -> None:
    self._submit_send(
        encode_message(
            "create_room",
            room_name=room_name,
            game_type=game_type.value,
        )
    )
```

다른 네트워크 메서드와 전용 asyncio 스레드 구조는 변경하지 않는다.

## 8. Create Room UI

현재 Canvas 모달에 게임 선택 영역과 Othello 전용 Board Size selector를 추가한다.

```text
Create Room

Room Name  [                         ]

Game       (●) Gomoku
           ( ) Othello

Board Size [ 10 × 10 ▼ ]

               [Cancel] [Create]
```

구현 요구:

- 기본 선택은 GOMOKU
- 모달을 열 때 이전 선택을 초기화
- Create 버튼은 Room Name과 Game Type이 모두 유효할 때만 요청
- 요청 중에는 중복 제출 차단
- `INVALID_GAME_TYPE` 및 기존 Room Name 오류를 모달/상태 메시지에 표시
- 모달을 닫거나 disconnect하면 선택 변수와 pending 상태 정리

GUI 표시 문자열은 `Gomoku`, `Othello`를 사용하고 wire에는 enum의 대문자 값을 보낸다.

## 9. Lobby Room 카드

Room 카드에 게임 종류를 표시한다.

```text
친선 오셀로
Othello · 8x8
1 / 2 · WAITING
```

Room ID는 현재처럼 내부 선택 키로 사용하고 화면에는 노출하지 않아도 된다.

Room List snapshot이 갱신되어도 동일한 `room_id`의 선택 상태는 유지한다. 선택된 Room이
사라졌거나 새 snapshot에서 입장 불가 상태가 되면 Join 버튼을 비활성화한다.

알 수 없는 `game_type`이 있는 Room 항목은 전체 snapshot을 부분 적용하지 말고 protocol
error로 처리한다.

## 10. 게임 화면 구조

Game 정보 영역에 게임 종류와 오셀로 점수를 표시한다.

```text
Room: 친선 오셀로
Game: Othello
You: ●
Turn: ○
Score: Black 12 · White 8
Status: PLAYING
```

오목에서는 기존 Board/Win Length 표시를 유지한다. 오셀로에서는 서버가 확정한
`board_size × board_size`와 점수를 표시하고 Win Length는 숨긴다.

Restart, Leave Room, Disconnect 버튼과 확인 기반 상태 전환은 공통으로 재사용한다.

## 11. 보드 렌더링 분리

기존 오목판은 돌을 격자 교차점에 놓는다. 오셀로는 8×8 셀 중앙에 돌을 놓으므로 동일한
좌표 계산을 그대로 사용하면 가장자리와 클릭 영역이 부정확해진다.

권장 구조:

```text
BoardRenderer
├── GomokuBoardRenderer
│   └── 교차점 grid, 화점, 마지막 착수, 점선 preview
└── OthelloBoardRenderer
    └── N×N 셀, 녹색 배경, 셀 중앙 돌, 합법 수 표시
```

대규모 위젯 재작성 대신 현재 Canvas를 공유하고 다음 함수의 게임별 구현만 분리한다.

- pixel → board 좌표
- board 좌표 → 돌 중심
- grid/cell 배경 그리기
- 돌 그리기
- Hover/합법 수 표시
- 마지막 착수 표시
- 결과 overlay

오셀로 좌표는 `x=0..board_size-1`, `y=0..board_size-1` 셀 좌표이며
`board[y][x]`에 대응한다.

## 12. 오셀로 입력과 Hover

`AppState.can_move()`를 게임 종류별로 변경한다.

```text
공통
  connected
  IN_ROOM
  PLAYING
  current_turn == my_color
  좌표 범위 안
  빈 셀

GOMOKU
  위 공통 조건이면 전송 가능

OTHELLO
  위 공통 조건 + (x, y)가 서버 legal_moves에 포함
```

오셀로 Hover는 서버가 전달한 합법 수에만 표시한다. Hover 시 뒤집힐 돌을 클라이언트가
계산하거나 미리 변경하지 않는다.

클릭 후 서버 응답이 올 때까지 같은 착수의 중복 전송을 막기 위해 `move_pending`을 두는
것을 권장한다. `move_result` 또는 `error` 수신 시 해제한다.

## 13. 오셀로 메시지 적용

### move_result

검증 후 다음 순서로 반영한다.

1. `board[y][x]`에 착수 색 적용
2. `flipped[]` 좌표에 서버가 보낸 색 적용
3. `last_move=(x, y)`
4. `passed_color` 저장
5. `current_turn=next_turn`
6. 이전 `legal_moves` 비우기
7. 보드 redraw

뒤따르는 `game_state`가 board, score, legal moves를 최종 동기화한다.

### game_state

- board 전체 교체
- score 전체 교체
- legal_moves 전체 교체
- turn/status/result 교체
- 상태가 FINISHED면 legal_moves 비우기

pass가 발생하면 예를 들어 다음 상태 메시지를 표시한다.

```text
White has no legal move. Black moves again.
```

클라이언트가 pass 요청 메시지를 별도로 보내지는 않는다.

## 14. 결과 표시

오목 결과 overlay는 현재 문구와 금수 사유를 유지한다.

오셀로 결과는 서버의 winner/loser/score를 사용한다.

```text
You Win
Black 35 · White 29
```

```text
Draw
Black 32 · White 32
```

`reason`은 표시 보조 정보로만 사용하고 클라이언트 판정에 사용하지 않는다.

## 15. Restart와 플레이어 재배정

오셀로 Restart에서 서버가 `your_color`, `starting_color=BLACK`, 빈 초기 보드와 점수를
다시 보낸다.

클라이언트는 기존 오목과 동일하게 이전 색상을 유지한다고 가정하지 않는다. `restart`
또는 이어지는 `game_state`의 서버 값을 기준으로 다음을 교체한다.

- my_color
- current_turn
- board
- score
- legal_moves
- result
- passed_color
- last_move

상대가 나가면 현재 라운드 상태를 계속 플레이 가능한 것으로 두지 않는다.

## 16. 호환성 정책

서버 전환 기간에는 다음 정책을 사용할 수 있다.

- `connected.supported_game_types`가 없으면 GOMOKU만 지원하는 구버전 서버로 간주
- 구버전 Room 항목에 `game_type`이 없으면 GOMOKU로 간주
- 신규 서버가 명시한 알 수 없는 `game_type`은 거부
- OTHELLO에서 `win_length=null`을 정상값으로 허용

fallback은 구버전 호환 경계에서만 사용한다. 신규 Room 생성 요청에는 항상
`game_type`을 포함한다.

## 17. 파일별 작업 지시

### 신규 파일

- `omok_client/game_type.py`
  - GameType enum과 wire 변환
- `omok_client/board_renderer.py` 또는 동등한 모듈
  - 게임 종류별 Canvas 좌표와 렌더링 책임

### 수정 파일

- `omok_client/network.py`
  - `create_room(room_name, game_type, board_size=None)`
- `omok_client/state.py`
  - RoomSummary/AppState 확장
  - 게임별 settings와 payload 검증
  - flipped, score, legal_moves, pass 처리
- `omok_client/gui.py`
  - Create Room 게임 선택
  - Lobby 게임 종류 표시
  - 게임별 board renderer 선택
  - 오셀로 점수/pass/result 표시
- `omok_client/board.py`
  - 공통 geometry로 유지하거나 오목/오셀로 geometry 분리
- `README.md`
  - 지원 게임과 새 프로토콜 설명

## 18. 테스트 요구사항

### protocol/network

- GOMOKU/OTHELLO create_room 인코딩
- 알 수 없는 game_type 거부
- join_room은 room_id만 전송

### state

- Room List에 서로 다른 게임이 동시에 존재
- OTHELLO의 협상된 8/10/12 크기와 `win_length=null` 수용
- 잘못된 OTHELLO 보드 크기 거부
- joined의 game_type 저장
- flipped 다중 셀 반영
- authoritative game_state가 임시 상태를 교정
- score와 legal_moves 전체 교체
- 자동 pass 후 동일 색 차례 처리
- game_over 점수와 무승부 처리
- restart 시 색상과 초기 상태 교체
- 잘못된 메시지 적용 실패 시 기존 상태 보존

### GUI

- Create Room 기본값 GOMOKU
- Othello 선택 시 network 호출에 OTHELLO 전달
- Room 카드에 게임 종류 표시
- 오목은 교차점, 오셀로는 셀 중앙 좌표 사용
- Othello legal_moves 밖에서는 Hover/전송 없음
- 오셀로 점수와 pass 안내 표시
- 게임 전환 또는 퇴장 시 이전 renderer 상태 제거

### 회귀

- 기존 Room Name 정규화
- 오목 15×15/19×19 렌더링과 좌표 변환
- 오목 move_result/game_state/game_over
- 렌주 금수 결과 표시
- Restart 색상 변경
- disconnect/leave 후 Lobby 복귀

비렌더링 단위 테스트 통과만으로 Tk 화면이 정상이라고 단정하지 않는다. 마지막에는 실제
Tk 창에서 오목과 오셀로 Room을 각각 생성하고 resize, Hover, 클릭, 점수, pass, Restart,
Leave를 수동 확인한다.

## 19. 구현 순서

1. GameType과 wire 계약을 테스트로 고정
2. RoomSummary와 AppState를 game_type aware 구조로 변경
3. NetworkClient create_room 확장
4. Create Room 모달과 Lobby 카드 변경
5. 오셀로 state payload 적용
6. 게임별 board geometry/renderer 분리
7. 점수, pass, 결과, Restart UI 연결
8. 기존 오목 테스트 회귀
9. 두 클라이언트와 실제 서버를 사용한 통합 확인
10. README 및 서버 계약과 최종 필드 대조

## 20. 완료 조건

- 사용자가 Create Room에서 Gomoku 또는 Othello를 선택하고 Othello 크기를 선택할 수 있다.
- 요청에 정규화된 room_name과 game_type, Othello의 board_size가 함께 전송된다.
- Lobby에서 두 게임 종류를 구분하고 Room ID로 입장할 수 있다.
- joined 이후 올바른 게임 renderer가 선택된다.
- 오셀로의 배치, 뒤집기, pass, 점수와 종료가 서버 메시지대로 표시된다.
- 오셀로의 불법 위치를 전송하지 않으며 서버 오류에도 보드가 변하지 않는다.
- Restart, Leave, disconnect 후 게임별 임시 상태가 남지 않는다.
- 기존 오목 동작과 테스트가 유지된다.
- 클라이언트 전체 테스트와 실제 Tk 수동 검증 결과가 문서화된다.
