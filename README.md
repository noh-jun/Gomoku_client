# Python WebSocket Online Gomoku & Othello Client

Tkinter GUI와 `asyncio` WebSocket 통신을 분리한 온라인 오목·오셀로 클라이언트입니다. 서버가 게임의 authoritative state와 보드 설정을 가지며, 클라이언트는 서버에서 받은 `game_type`, `board`, `move_result`, `game_state`, `restart`를 검증한 뒤 화면에 반영합니다.

클라이언트 릴리스 버전은 `omok_client/version.py`의 `CLIENT_VERSION`에서 관리하며 Connection Settings 화면에 표시됩니다. 서버 버전 및 WebSocket 프로토콜 버전과는 별개의 값입니다.

## 구조

```text
client/
├── omok_client/
│   ├── __init__.py
│   ├── main.py       # 프로그램 진입 및 로깅
│   ├── board.py      # 동적 BoardGeometry와 양방향 좌표 변환
│   ├── board_renderer.py # 오셀로 8×8 셀 중심 좌표
│   ├── canvas_overlay.py # Canvas 기반 범용 클릭 해제 팝업
│   ├── client_settings.py # 서버 주소 설정 파일 저장 및 로드
│   ├── game_type.py  # GOMOKU/OTHELLO wire enum
│   ├── protocol.py   # 클라이언트 JSON 인코딩/디코딩
│   ├── room_name.py  # 방 이름 정규화와 입력 검증
│   ├── gui.py        # Connection/Lobby/Game 화면과 보드 렌더링
│   ├── network.py    # 별도 스레드의 asyncio/WebSocket 루프
│   ├── stone_image.py # You/Turn 돌 이미지 생성
│   └── state.py      # 서버 메시지 기반 AppState 변경
├── tests/
│   ├── test_gui.py
│   ├── test_client_settings.py
│   ├── test_hover_gui.py
│   ├── test_network.py
│   ├── test_othello_state.py
│   ├── test_protocol.py
│   ├── test_room_name.py
│   └── test_state.py
├── docs/
│   ├── room-name-server-contract.md # Room Name 송수신 계약
│   ├── othello-client-development-guide.md # 오목·오셀로 클라이언트 개발 지시서
│   └── othello-board-size-client-development-guide.md # Room별 오셀로 크기 선택 지시서
├── client.py
├── client_settings.json # 최초 Save 후 생성되는 로컬 설정(Git 제외)
├── requirements.txt
└── README.md
```

## 실행 환경과 설치

Python 3.11 이상을 권장합니다. PowerShell에서 클라이언트 전용 가상환경까지 `client/` 안에 만들려면 다음을 실행합니다.

```powershell
cd client
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe client.py
```

저장소 루트에 이미 만든 `.venv`를 계속 사용할 수도 있습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\client\requirements.txt
.\.venv\Scripts\python.exe .\client\client.py
```

Windows에서는 `client` 폴더의 실행 스크립트를 사용할 수도 있습니다. 클라이언트 전용 `.venv`가 있으면 우선 사용하고, 없으면 상위 폴더의 `.venv`를 자동으로 사용합니다.

```powershell
cd client
.\run_client.cmd
```

클라이언트를 실행해 Server 주소로 연결하면 Lobby가 열립니다. Room ID를 직접 입력하지 않고 서버가 제공한 Room 목록에서 선택하거나 새 Room을 만듭니다. 기본 접속 URL은 다음과 같습니다.

```text
ws://192.168.1.75:8000/ws
```

서버는 별도 실행되어 있어야 합니다. TLS 서버는 `wss://` 주소도 사용할 수 있습니다.

최초 Connection 화면에는 Connect 버튼과 우하단 설정 아이콘만 표시됩니다. 설정 아이콘을 누르면 Connection 화면 내부의 Canvas 팝업에서 Server URL을 변경할 수 있습니다. Save 시 개발 환경에서는 `client/client_settings.json`, 배포 실행 파일에서는 실행 파일 옆의 `client_settings.json`에 저장하고 다음 실행부터 자동으로 불러옵니다. 설정 파일이 없거나 JSON 또는 서버 주소가 잘못되면 기본 주소를 사용합니다. 로컬 설정 파일은 Git에서 제외됩니다.

## 동작 구조

- 메인 스레드는 Tkinter `mainloop()`와 모든 위젯 변경을 담당합니다.
- 네트워크 데몬 스레드는 전용 asyncio 이벤트 루프와 WebSocket을 담당합니다.
- 네트워크 스레드는 `queue.Queue`에 이벤트를 넣고, GUI는 `root.after()`로 큐를 주기적으로 처리합니다.
- GUI의 전송 요청은 `asyncio.run_coroutine_threadsafe()`로 네트워크 루프에 전달됩니다.
- 화면 상태는 `DISCONNECTED`, `LOBBY`, `IN_ROOM`으로 분리합니다. 최초에는 Connection 페이지만 표시하고 서버의 `connected` 확인을 받은 뒤 Room List가 있는 Lobby 페이지로 전환합니다. Room 입장 후에는 Game 페이지를 표시하며 연결 해제 시 Connection 페이지로 돌아갑니다.
- Lobby는 서버 `room_list` 스냅샷을 여러 열의 Room 카드로 실시간 반영합니다. 각 카드는 Room 이름·게임 종류·보드 크기·인원·상태를 표시하고, `room_id`는 화면에 노출하지 않은 채 선택과 입장 요청의 내부 키로만 사용합니다. Create Room Canvas 모달에서 Gomoku 또는 Othello를 선택할 수 있으며 신규 요청에는 항상 `game_type`을 포함합니다.
- 클릭 시 로컬 보드를 먼저 변경하지 않습니다. 서버의 `move_result`가 도착해야 돌이 표시되며, 응답 전까지 같은 착수의 중복 전송을 막습니다.
- 오목 착수 제한 시간은 서버가 보낸 `turn_remaining_ms`를 수신한 뒤 로컬 monotonic clock으로만 감소시킵니다. PC의 날짜·시간 설정은 계산에 사용하지 않으며 실제 턴 만료는 서버가 판정합니다.
- Restart 버튼도 요청만 보내며, 서버의 `restart`가 도착해야 보드를 초기화합니다.
- 오목은 기존 `BoardGeometry`로 15×15/19×19 교차점 좌표를 사용합니다. 오셀로는 `OthelloBoardGeometry`로 녹색 8×8 셀과 셀 중앙 좌표를 사용합니다. 두 렌더러 모두 resize 후 좌표를 다시 계산합니다.
- 오목 Hover는 내 차례의 빈 교차점에, 오셀로 Hover와 합법 수 표시는 서버가 보낸 `legal_moves`에만 나타납니다. 클라이언트는 뒤집을 돌이나 pass를 직접 계산하지 않습니다.
- 오셀로 `move_result.flipped`는 서버가 지정한 셀을 즉시 갱신하고, 뒤이어 받은 authoritative `game_state`가 board·score·legal moves 전체를 교정합니다.
- 서버가 `connected.room_creation_options.OTHELLO`에 제한시간과 `RANDOM_LEGAL_MOVE` 동작을 광고하면 오셀로 방에서도 Turn Timer를 선택할 수 있습니다. 시간 초과 시 `turn_timeout`은 비차단 안내만 표시하고, 실제 자동 착수와 뒤집기는 뒤이어 오는 `move_result`와 authoritative `game_state`로 반영합니다. capability가 없는 구버전 서버에서는 오셀로 제한시간을 비활성화합니다.
- 선공 색상과 현재 턴은 서버의 `starting_color`, `current_turn`을 따르므로 WHITE 선공도 지원합니다. 종료 시 정상 승패·무승부 및 `DOUBLE_THREE`, `DOUBLE_FOUR`, `OVERLINE` 금수 원인을 메인 화면에 표시합니다.
- 승패 또는 무승부가 확정되면 최종 보드를 유지한 채 결과를 보드 중앙에 표시합니다. 오목은 기존 금수 사유를, 오셀로는 서버 winner와 `Black n · White n` 점수를 표시합니다.
- 보드 중앙 안내는 범용 `CanvasOverlay`를 사용합니다. 승패와 금수 착수 안내 팝업은 클릭하면 닫히며, 닫는 클릭은 착수 입력으로 전달되지 않습니다.
- Restart 응답의 새로운 `your_color`를 즉시 적용하므로 라운드 사이 BLACK/WHITE 재배정과 새 색상 Preview를 지원합니다.
- WebSocket 미연결 상태와 Lobby에서는 바둑판을 표시하지 않으며, `joined`로 Room 입장이 확정된 Game 화면에서만 표시합니다.
- Connection 페이지에는 저장된 서버 주소를 사용하는 Connect 버튼과 우하단 설정 아이콘만 표시합니다. 설정은 별도 창이 아닌 Canvas 팝업에서 편집합니다. Lobby 페이지는 연결된 서버·Disconnect·Room 목록·Create·Join을, Game 페이지는 Room·You·Turn·Status·Board 설정·Restart·Leave Room·Disconnect를 소유합니다.
- Game 영역의 You와 Turn 값은 `BLACK`/`WHITE` 문자열 대신 흑돌·백돌 이미지 아이콘으로 표시하며, 색상이나 턴이 없으면 빈 아이콘으로 표시합니다.

## 프로토콜

Client → Server 메시지는 `get_room_list`, `create_room`, `join_room`, `leave_room`, `move`, `chat`, `restart_request`, `ping`을 사용합니다. `chat`은 `text` 하나를 전송하며 Room 전원에게 `chat_message`로 되돌아옵니다([계약](docs/room-chat-client-contract.md)). `create_room`은 `room_name`과 `GOMOKU` 또는 `OTHELLO`의 `game_type`을 전송합니다. Server → Client 메시지는 `connected`, `room_list`, `room_created`, `joined`, `left_room`, `player_joined`, `game_start`, `move_result`, `game_over`, `game_state`, `player_disconnected`, `chat_message`, `restart`, `error`, `pong`을 처리합니다.

서버 연결 주소는 `/ws`이며 Room ID를 URL에 포함하지 않습니다. `connected.supported_game_types`가 없으면 구버전 서버로 보고 Gomoku만 생성할 수 있습니다. `room_list`, `room_created`, `joined`의 명시적인 알 수 없는 `game_type`은 거부합니다. 현재 구현은 오셀로 `board_size: 8`, `win_length: null`만 허용합니다. 전체 계약은 [오셀로 클라이언트 개발 가이드](docs/othello-client-development-guide.md)를 참고하십시오. Room별 8/10/12 크기 선택 후속 작업은 [오셀로 보드 크기 클라이언트 개발 지시서](docs/othello-board-size-client-development-guide.md)를 따릅니다.

서버는 `joined`에 `board_size`와 `win_length`를 포함해야 하며, 동기화를 위해 `game_start`, `game_state`, `restart`에도 같은 필드를 포함할 수 있습니다. `game_state.board`는 `board_size`개의 행과 열을 가진 `board[y][x]` 배열이어야 하고 셀 값은 `"BLACK"`, `"WHITE"`, `null`입니다. 호환성을 위해 빈 셀의 `"EMPTY"`와 빈 문자열도 허용합니다. 구버전 서버가 설정 필드를 생략하면 15×15, 승리 길이 5의 현재 설정을 유지합니다.

게임 규칙과 라운드 재배정을 위해 서버는 다음 필드를 전달할 수 있습니다.

- `joined`: `starting_color`
- `game_start`: `game_type`, `your_color`, `starting_color`, `current_turn`, `board_size`, `win_length`
- `move_result`: `game_type`, `x`, `y`, `color`, `next_turn`; 오셀로는 `flipped`, `passed_color` 추가
- `game_over`: `game_type`, `winner`, `loser`, `reason`, `forbidden_type`, `message`, `x`, `y`; 오셀로는 `score` 추가
- `game_state`: `game_type`, `starting_color`, `current_turn`, `winner`, `loser`, `status`, `game_over_reason`, `forbidden_type`, `board`, `turn_remaining_ms`, `turn_revision`; 오셀로는 `score`, `legal_moves` 추가
- `restart`: `game_type`, `your_color`, `starting_color`, `current_turn`, `board_size`, `win_length`

`reason: "forbidden_move"`일 때 `forbidden_type`은 `DOUBLE_THREE`, `DOUBLE_FOUR`, `OVERLINE` 중 하나입니다. 클라이언트는 이를 표시만 하며 금수 또는 승패를 직접 판정하지 않습니다. 종료 상태는 `FINISHED`로 표시하고 보드와 마지막 착수는 그대로 유지합니다.

```json
{
  "type": "joined",
  "room_id": "abc123",
  "room_name": "친선 대국",
  "game_type": "GOMOKU",
  "your_color": "BLACK",
  "board_size": 19,
  "win_length": 5
}
```

오목은 `board_size` 5~50과 `win_length` 3~`board_size`를 허용합니다. 오셀로는 8×8과 `win_length: null`만 허용하며, `score`, `legal_moves`, `flipped`, 결과는 서버가 계산합니다.

알 수 없는 메시지, 잘못된 JSON, 유효하지 않은 상태 메시지는 기록하고 화면 메시지로 표시하되 GUI를 종료하지 않습니다.

## 테스트

```powershell
cd client
.\.venv\Scripts\python.exe -m unittest discover -v
```

오목 15×15/19×19 교차점과 오셀로 8×8 셀 중심 좌표, 게임 종류별 Room 생성, 혼합 Room 목록, flipped, score, legal moves, pass, 결과, restart, 잘못된 상태의 원자적 거부를 테스트합니다. 자동화 테스트는 실제 Tk 화면이나 서버 통합을 증명하지 않으므로 두 클라이언트로 Gomoku/Othello를 각각 생성해 수동 확인해야 합니다.
