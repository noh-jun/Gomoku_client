# 오셀로 Room별 보드 크기 선택 클라이언트 개발 지시서

## 1. 목적과 범위

오셀로 Room을 만들 때 사용자가 보드 크기를 선택할 수 있도록 클라이언트를 확장한다.

오목 보드 크기는 계속 서버 운영 설정을 따른다. 따라서 오목 Room 생성 화면에는 보드
크기 선택을 표시하지 않고, `create_room`에도 `board_size`를 보내지 않는다. 오셀로만
Room 생성 요청에 선택한 `board_size`를 포함한다.

초기 지원값은 다음과 같이 정의한다.

```text
OTHELLO_BOARD_SIZES = (8, 10, 12)
DEFAULT_OTHELLO_BOARD_SIZE = 10
```

이 값은 클라이언트에 영구 고정하지 않는다. 신규 서버가 연결 응답으로 제공한 실제
지원값을 우선 사용한다. 위 값은 향후 서버 구현의 초기 정책이자 UI/테스트 기준이다.

이 문서는 기존
[`othello-client-development-guide.md`](./othello-client-development-guide.md)의
오셀로 보드 크기 고정 규칙을 대체한다. 게임 규칙, `flipped`, `legal_moves`, 점수,
Restart 등에 관한 나머지 계약은 기존 문서를 그대로 따른다.

## 2. 핵심 정책

- `GOMOKU`: 보드 크기를 서버가 정하며 Room 생성 요청에서 선택하지 않는다.
- `OTHELLO`: 보드 크기를 Room 생성자가 `8`, `10`, `12` 중 선택한다.
- 서버가 광고한 허용 목록이 있으면 그 목록만 UI에 표시하고 전송한다.
- 서버가 오셀로를 지원하지만 크기 목록을 광고하지 않으면 구버전으로 보고 `8`만 허용한다.
- 서버가 오셀로를 지원하지 않으면 기존처럼 Othello 선택 자체를 비활성화한다.
- Room의 실제 크기는 요청값이 아니라 `joined.board_size`와 `game_state.board_size`가
  최종 권위값이다.
- 같은 Room 안에서 `board_size`는 Restart를 포함한 Room 수명 동안 바뀌지 않는다.
- 클라이언트는 임의의 짝수를 만들어 보내지 않는다. 서버가 광고한 allowlist만 사용한다.

## 3. 향후 서버 WebSocket 계약

이 절은 서버 개발 시 구현해야 할 계약이다. 현재 서버가 아직 이 필드를 제공하지 않아도
클라이언트는 8×8 fallback으로 동작해야 한다.

### 3.1 연결 기능 광고

신규 서버의 `connected` 메시지에 Room 생성 옵션을 추가한다.

```json
{
  "type": "connected",
  "supported_game_types": ["GOMOKU", "OTHELLO"],
  "room_creation_options": {
    "OTHELLO": {
      "board_sizes": [8, 10, 12],
      "default_board_size": 10
    }
  },
  "game_type": "GOMOKU",
  "board_size": 15,
  "win_length": 5,
  "starting_color": "WHITE"
}
```

`room_creation_options`는 Room 생성 시 클라이언트가 선택할 수 있는 값만 표현한다.
오목의 `board_size`는 서버 운영 설정이므로 이 객체에 `GOMOKU.board_sizes`를 넣지 않는다.

검증 규칙:

- `room_creation_options`가 있으면 JSON object여야 한다.
- `OTHELLO.board_sizes`는 중복 없는 비어 있지 않은 정수 배열이어야 한다.
- 모든 크기는 4 이상인 짝수여야 한다. 초기 서버 정책은 `8`, `10`, `12`만 광고한다.
- `default_board_size`는 반드시 `board_sizes` 안에 있어야 한다.
- 알 수 없는 게임 key 또는 잘못된 값이 있으면 해당 `connected`를 protocol error로
  처리하고 부분 적용하지 않는다.

### 3.2 오셀로 Room 생성

```json
{
  "type": "create_room",
  "room_name": "10칸 오셀로",
  "game_type": "OTHELLO",
  "board_size": 10
}
```

신규 클라이언트는 Othello 생성 시 `board_size`를 반드시 보낸다. 향후 서버는 허용 목록에
없는 값, 홀수, boolean, 문자열을 `INVALID_BOARD_SIZE`로 거부한다.

전환 기간 동안 구버전 클라이언트가 Othello 생성 요청에서 `board_size`를 생략하면 서버는
8을 사용할 수 있다. 이 fallback은 호환용이며 신규 클라이언트 동작으로 사용하지 않는다.

오목 생성 요청은 기존과 같다.

```json
{
  "type": "create_room",
  "room_name": "오목 대국",
  "game_type": "GOMOKU"
}
```

오목 요청에는 `board_size`를 넣지 않는다. 클라이언트가 실수로 넣더라도 서버는 운영 설정을
우선해야 하지만, 클라이언트 테스트에서는 애초에 해당 필드가 인코딩되지 않는지 확인한다.

### 3.3 서버 응답의 실제 크기

`room_created`, `room_list`, `joined`, `game_start`, `game_state`, `restart`는 해당 Room의
실제 `board_size`를 전달한다. 최소 예시는 다음과 같다.

```json
{
  "type": "room_created",
  "room_id": "room_010",
  "room_name": "10칸 오셀로",
  "game_type": "OTHELLO",
  "board_size": 10
}
```

```json
{
  "type": "joined",
  "room_id": "room_010",
  "room_name": "10칸 오셀로",
  "game_type": "OTHELLO",
  "your_color": "BLACK",
  "board_size": 10,
  "win_length": null,
  "starting_color": "BLACK"
}
```

```json
{
  "room_id": "room_010",
  "room_name": "10칸 오셀로",
  "game_type": "OTHELLO",
  "board_size": 10,
  "win_length": null,
  "players": 1,
  "max_players": 2,
  "status": "WAITING"
}
```

클라이언트가 보낸 선택값과 서버 응답이 다르면 서버 응답을 적용한다. 단, 서버가 광고한
목록 밖의 크기이거나 동일 Room의 앞선 응답과 크기가 달라지면 조용히 교정하지 말고
protocol error로 처리한다.

### 3.4 오류

추가 오류 코드는 다음과 같다.

```text
INVALID_BOARD_SIZE
```

오류가 발생하면 Create Room 모달을 닫지 않고 선택값과 방 이름을 유지하여 사용자가 바로
수정할 수 있게 한다. 기존 `INVALID_GAME_TYPE`, `INVALID_ROOM_NAME`, `ROOM_NAME_TAKEN`도
같은 위치에 표시한다.

## 4. 현재 코드와 변경 지점

현재 구현에서 확인된 고정 결합은 다음과 같다.

- `omok_client/state.py`
  - `OTHELLO_BOARD_SIZE = 8` 상수
  - `_validate_game_settings()`가 Othello를 정확히 8×8로 제한
  - `_settings_from_message()`와 `_validated_rooms()`의 Othello 기본값이 8
- `omok_client/network.py`
  - `create_room(room_name, game_type)`만 받고 `board_size`를 보내지 않음
- `omok_client/gui.py`
  - Create Room 모달에 Game 선택만 있고 크기 선택이 없음
  - 모달을 열고 닫을 때 Game Type만 초기화
- `omok_client/board_renderer.py`와 `gui.py`
  - 좌표 계산과 반복 렌더링은 대부분 `board_size` 기반이어서 구조 재작성은 불필요
- `tests/test_othello_state.py`
  - 10×10 Othello를 잘못된 설정으로 기대하는 테스트가 있음

따라서 네트워크 요청, capability 상태, 게임별 검증, Create Room 모달만 확장하고 기존
renderer 구조를 유지한다.

## 5. 클라이언트 데이터 모델

고정 단일 크기 상수를 fallback과 초기 정책으로 분리한다.

```python
LEGACY_OTHELLO_BOARD_SIZE = 8
DEFAULT_OTHELLO_BOARD_SIZES = (8, 10, 12)
DEFAULT_OTHELLO_BOARD_SIZE = 10
```

`AppState`에는 연결된 서버가 광고한 생성 옵션을 저장한다.

```python
othello_board_sizes: tuple[int, ...] = (LEGACY_OTHELLO_BOARD_SIZE,)
default_othello_board_size: int = LEGACY_OTHELLO_BOARD_SIZE
```

권장 사항:

- 가변 `list` 대신 정렬된 `tuple`로 저장한다.
- `connected` 전체 검증이 성공한 뒤 두 필드를 함께 교체한다.
- disconnect 시 `(8,)`, 기본값 `8`로 되돌린다.
- `supported_game_types`에 OTHELLO가 없으면 크기 목록은 UI에서 사용하지 않는다.
- Room 및 현재 게임의 `board_size`는 기존 `RoomSummary.board_size`와
  `AppState.board_size`를 계속 사용한다. 별도 Othello Room 크기 필드는 만들지 않는다.

## 6. 상태 검증 변경

기존의 `board_size == 8` 검사를 제거하고 검증 문맥을 분리한다.

```text
Room 생성 옵션 검증
  connected에서 광고한 Othello allowlist 검증

Lobby Room 검증
  OTHELLO board_size가 협상된 allowlist 안에 있는지 검증
  win_length는 null

현재 Room 메시지 검증
  joined에서 board_size 확정
  이후 game_start/game_state/restart는 확정된 크기와 동일해야 함
  starting_color는 BLACK, win_length는 null
```

서버 capability가 없는 구버전 연결에서는 협상된 allowlist를 `(8,)`로 간주한다.

`game_state` 검증은 동적 크기를 사용한다.

- `board` 행 개수와 각 행 길이: 정확히 `board_size`
- 모든 `legal_moves`, `flipped`, `last_move`: `0 <= x,y < board_size`
- `score.BLACK`, `score.WHITE`: 0 이상이며 각각 `board_size²` 이하
- authoritative `game_state`에서는 두 점수 합이 보드의 non-null 셀 수와 일치
- `legal_moves`는 중복이 없고 현재 board의 빈 셀만 가리킴

메시지 검증 중 실패하면 기존 AppState를 전혀 변경하지 않는다.

## 7. NetworkClient 변경

게임 종류에 따라 `board_size` 포함 여부를 명시적으로 결정한다.

```python
def create_room(
    self,
    room_name: str,
    game_type: GameType,
    board_size: int | None = None,
) -> None:
    fields: dict[str, object] = {
        "room_name": room_name,
        "game_type": game_type.value,
    }
    if game_type is GameType.OTHELLO:
        if board_size is None:
            raise ValueError("Othello board_size is required")
        fields["board_size"] = board_size
    elif board_size is not None:
        raise ValueError("Gomoku board_size is selected by the server")
    self._submit_send(encode_message("create_room", **fields))
```

GUI에서 검증했더라도 NetworkClient 경계에서 다시 검사한다. 문자열, boolean, 홀수 또는
허용 목록 밖 값은 GUI가 전달하지 않도록 하고, NetworkClient 단위 테스트는 `None`과
Gomoku에 잘못 전달된 크기를 거부하는지 확인한다.

## 8. Create Room UI

현재 Canvas 모달에 Othello 선택 시에만 활성화되는 Board Size 영역을 추가한다.

```text
Create Room

Room Name  [                              ]

Game       (●) Gomoku    ( ) Othello

Board Size [ 10 × 10 ▼ ]    ← Othello일 때만 표시/활성

                         [Cancel] [Create]
```

구현 요구:

- 모달 기본 Game은 기존대로 GOMOKU다.
- GOMOKU 선택 중에는 Board Size를 숨기거나 disabled 처리한다.
- OTHELLO로 변경하면 서버의 `default_othello_board_size`를 선택한다.
- 목록은 `othello_board_sizes`로 만들고 직접 숫자를 입력할 수 없게 한다.
- 예: `8 × 8`, `10 × 10`, `12 × 12`로 표시하되 내부 값은 정수다.
- Game을 Gomoku로 되돌렸다가 다시 Othello로 선택하면 서버 기본값으로 초기화한다.
- 모달을 새로 열거나 disconnect하면 임시 선택값을 초기화한다.
- 요청 pending 중에는 Game, Board Size, Room Name, Create 버튼을 모두 비활성화한다.
- 서버 오류 시 모달을 유지하고 오류 라벨을 표시한다.

필요한 GUI 상태 예:

```python
self._create_room_board_size_var = tk.IntVar(value=8)
```

기존 모달 높이를 늘리고 Board Size 행과 버튼이 겹치지 않도록 실제 Tk 창에서 확인한다.

## 9. Lobby와 Game 화면

Lobby Room 카드는 서버가 보낸 실제 크기를 그대로 표시한다.

```text
10칸 오셀로
Othello · 10 × 10
1 / 2 · WAITING
```

Game 화면도 고정 `8x8` 문구를 사용하지 않고 `AppState.board_size`로 표시한다. renderer는
현재처럼 매 redraw 시 동적 geometry를 계산한다.

큰 판에서 확인할 UI 조건:

- 10×10과 12×12 모두 Canvas 안에 잘리지 않고 들어가야 한다.
- 셀 크기 감소에 맞춰 돌 반지름, 합법 수 marker, 마지막 착수 marker를 비례 조정한다.
- 창 resize 후 pixel/board 양방향 좌표가 같은 셀을 가리켜야 한다.
- 작은 셀에서도 인접 칸 클릭 영역이 겹치지 않아야 한다.
- 점수는 최대 `board_size²`까지 레이아웃이 흔들리지 않아야 한다.

클라이언트는 크기에 따른 초기 돌 위치나 합법 수를 계산하지 않는다. 보드, 점수,
합법 수는 계속 서버 `game_state`를 따른다.

## 10. 파일별 작업 지시

### `omok_client/state.py`

- 고정 `OTHELLO_BOARD_SIZE` 검증 제거
- 서버 capability와 legacy fallback 상태 추가
- Room 목록과 joined 이후 메시지의 크기 일관성 검증
- 동적 board/score/legal_moves/flipped 검증

### `omok_client/network.py`

- `create_room(room_name, game_type, board_size=None)`로 확장
- Othello에만 `board_size` 직렬화
- Gomoku에 Room별 크기가 전달되는 것을 차단

### `omok_client/gui.py`

- Board Size selector와 상태 변수 추가
- Game radio 변경 시 selector 표시·초기화
- 선택값을 NetworkClient에 전달
- 오류/pending/close/disconnect 상태 정리

### `omok_client/board_renderer.py`

- 새로운 renderer 종류를 만들지 않는다.
- 8/10/12 크기에서 현재 동적 geometry와 marker 비율을 검증하고 필요한 수치만 보정한다.

### 문서

- `client/README.md`에서 Othello 8×8 고정 문구 제거
- `create_room` payload와 capability fallback 설명 추가
- 서버 구현 후 실제 광고 목록과 기본값을 이 문서와 다시 대조

## 11. 테스트 요구사항

### Network/protocol

- Othello 8/10/12 생성 요청에 해당 `board_size` 포함
- Gomoku 생성 요청에 `board_size`가 없음
- Othello `board_size=None`, 문자열, boolean, 홀수, 미지원 크기 거부
- `connected.room_creation_options` 정상/누락/빈 목록/중복/잘못된 기본값 검증
- capability 누락 시 Othello `(8,)`, 기본값 `8` fallback

### State

- 8×8, 10×10, 12×12 RoomSummary 수용
- 광고 목록 밖 Othello Room 거부
- 10×10 joined/game_start/game_state/restart 수용
- 동일 Room에서 10→12처럼 크기가 바뀌는 후속 메시지 거부
- 각 크기에서 board 행/열, legal_moves, flipped 좌표 경계 검증
- 점수 범위와 board 점유 수 불일치 거부
- 실패한 메시지가 기존 상태를 부분 변경하지 않음

### GUI

- Gomoku 기본 선택에서는 크기 selector 미표시 또는 disabled
- Othello 선택 시 서버 기본 크기 선택
- 8/10/12 선택값이 network 호출에 전달됨
- 서버가 `[8, 12]`만 광고하면 10이 UI에 나타나지 않음
- 구버전 서버에서는 8만 표시
- 모달 close/disconnect/reopen 시 임시 선택 초기화
- Lobby 카드와 Game 정보에 실제 크기 표시

### Renderer/수동 검증

- 8×8, 10×10, 12×12 각각 중앙/네 모서리 pixel 좌표 왕복 테스트
- 각 크기에서 resize, Hover, legal marker, 클릭, 뒤집기, 마지막 착수 표시 확인
- 12×12에서 돌과 marker가 인접 셀을 침범하지 않는지 실제 Tk 화면 확인
- 두 클라이언트로 서로 다른 크기의 Othello Room을 동시에 만들어 상태가 섞이지 않는지 확인

## 12. 구현 순서

1. capability와 새 `create_room` wire 계약 테스트 작성
2. AppState에 Othello 생성 옵션과 legacy fallback 추가
3. 고정 8×8 설정 검증을 동적 allowlist/현재 Room 검증으로 교체
4. NetworkClient의 조건부 `board_size` 인코딩 구현
5. Create Room 모달 selector와 pending/error 처리 구현
6. Lobby/Game 크기 표시 확인
7. 8/10/12 renderer 자동 테스트와 실제 Tk 수동 확인
8. 서버 구현 후 WebSocket 통합 테스트
9. README 및 두 오셀로 개발 문서의 최종 계약 동기화

## 13. 완료 조건

- 사용자가 Othello Room 생성 시 서버가 허용한 보드 크기를 선택할 수 있다.
- 초기 신규 서버 기준으로 8×8, 10×10, 12×12가 표시되고 기본값은 10×10이다.
- Gomoku Room 생성 동작과 서버 운영 보드 설정은 변하지 않는다.
- 신규 Othello 요청에는 `game_type`과 정수 `board_size`가 함께 전송된다.
- Room 목록, 입장, 게임 진행, Restart가 Room의 실제 크기를 끝까지 유지한다.
- 구버전 서버에서는 별도 오류 없이 8×8만 선택할 수 있다.
- 잘못되거나 협상되지 않은 크기는 전송·적용되지 않는다.
- 8/10/12 렌더링, 좌표 변환, 합법 수, 점수, pass, 결과 화면이 정상이다.
- 자동 테스트와 실제 Tk 다중 크기 수동 검증 결과가 기록된다.
