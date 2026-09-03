# Python WebSocket Online Omok Client

Tkinter GUI와 `asyncio` WebSocket 통신을 분리한 온라인 오목 클라이언트입니다. 서버가 게임의 authoritative state와 보드 설정을 가지며, 클라이언트는 서버에서 받은 `board_size`, `move_result`, `game_state`, `restart`를 화면에 반영합니다.

## 구조

```text
client/
├── omok_client/
│   ├── __init__.py
│   ├── main.py       # 프로그램 진입 및 로깅
│   ├── board.py      # 동적 BoardGeometry와 양방향 좌표 변환
│   ├── protocol.py   # 클라이언트 JSON 인코딩/디코딩
│   ├── gui.py        # Tkinter UI와 보드 렌더링
│   ├── network.py    # 별도 스레드의 asyncio/WebSocket 루프
│   └── state.py      # 서버 메시지 기반 AppState 변경
├── tests/
│   ├── test_gui.py
│   ├── test_protocol.py
│   └── test_state.py
├── client.py
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

두 클라이언트를 실행해 Server와 Room에 같은 값을 입력한 뒤 Connect를 누릅니다. 기본 접속 URL은 다음과 같이 조합됩니다.

```text
ws://192.168.1.75:8000/ws/abc123
```

서버는 별도 실행되어 있어야 합니다. TLS 서버는 `wss://` 주소도 사용할 수 있습니다.

## 동작 구조

- 메인 스레드는 Tkinter `mainloop()`와 모든 위젯 변경을 담당합니다.
- 네트워크 데몬 스레드는 전용 asyncio 이벤트 루프와 WebSocket을 담당합니다.
- 네트워크 스레드는 `queue.Queue`에 이벤트를 넣고, GUI는 `root.after()`로 큐를 주기적으로 처리합니다.
- GUI의 전송 요청은 `asyncio.run_coroutine_threadsafe()`로 네트워크 루프에 전달됩니다.
- 클릭 시 로컬 보드를 먼저 변경하지 않습니다. 서버의 `move_result`가 도착해야 돌이 표시됩니다.
- Restart 버튼도 요청만 보내며, 서버의 `restart`가 도착해야 보드를 초기화합니다.
- Canvas 크기와 논리 보드 크기를 분리하며, 창 크기가 바뀌면 동일한 `BoardGeometry`로 격자·돌·마지막 착수·클릭 좌표를 다시 계산합니다.
- 서버가 전달한 크기에 따라 15×15와 19×19를 포함한 보드를 공통 계산식으로 렌더링합니다.
- 내 차례의 빈 교차점에 마우스를 올리면 자신의 돌 색상과 대응하는 점선 윤곽 Preview Stone을 표시합니다. Hover와 Click은 동일한 `BoardGeometry.pixel_to_board()`와 착수 가능 조건을 공유하며 Hover만으로는 서버 메시지를 전송하지 않습니다.
- 선공 색상과 현재 턴은 서버의 `starting_color`, `current_turn`을 따르므로 WHITE 선공도 지원합니다. 종료 시 정상 승패·무승부 및 `DOUBLE_THREE`, `DOUBLE_FOUR`, `OVERLINE` 금수 원인을 메인 화면에 표시합니다.
- Restart 응답의 새로운 `your_color`를 즉시 적용하므로 라운드 사이 BLACK/WHITE 재배정과 새 색상 Preview를 지원합니다.
- WebSocket 미연결 상태에서는 바둑판을 표시하지 않으며, 연결 완료 시 격자를 표시하고 연결 종료 시 즉시 지웁니다.
- 보드 위의 상단 UI는 `Connection`과 `Game` 영역으로 분리합니다. Server·Room·Connect는 연결 영역이 소유하고, You·Turn·Status·Board 설정·Restart는 게임 영역이 소유합니다. 하단은 게임 상태 메시지 전용입니다.

## 프로토콜

Client → Server 메시지는 `move`, `restart_request`, `ping`을 사용합니다. Server → Client 메시지는 `joined`, `player_joined`, `game_start`, `move_result`, `game_over`, `game_state`, `player_disconnected`, `restart`, `error`, `pong`을 처리합니다.

서버는 `joined`에 `board_size`와 `win_length`를 포함해야 하며, 동기화를 위해 `game_start`, `game_state`, `restart`에도 같은 필드를 포함할 수 있습니다. `game_state.board`는 `board_size`개의 행과 열을 가진 `board[y][x]` 배열이어야 하고 셀 값은 `"BLACK"`, `"WHITE"`, `null`입니다. 호환성을 위해 빈 셀의 `"EMPTY"`와 빈 문자열도 허용합니다. 구버전 서버가 설정 필드를 생략하면 15×15, 승리 길이 5의 현재 설정을 유지합니다.

게임 규칙과 라운드 재배정을 위해 서버는 다음 필드를 전달할 수 있습니다.

- `joined`: `starting_color`
- `game_start`: `starting_color`, `current_turn`
- `game_over`: `winner`, `loser`, `reason`, `forbidden_type`, `message`, `x`, `y`
- `game_state`: `starting_color`, `current_turn`, `winner`, `loser`, `status`, `game_over_reason`, `forbidden_type`
- `restart`: `your_color`, `starting_color`, `current_turn`, `board_size`, `win_length`

`reason: "forbidden_move"`일 때 `forbidden_type`은 `DOUBLE_THREE`, `DOUBLE_FOUR`, `OVERLINE` 중 하나입니다. 클라이언트는 이를 표시만 하며 금수 또는 승패를 직접 판정하지 않습니다. 종료 상태는 `FINISHED`로 표시하고 보드와 마지막 착수는 그대로 유지합니다.

```json
{
  "type": "joined",
  "room_id": "abc123",
  "your_color": "BLACK",
  "board_size": 19,
  "win_length": 5
}
```

클라이언트는 안전을 위해 `board_size` 5~50과 `win_length` 3~`board_size`만 허용합니다. 승리 판정은 여전히 서버 책임입니다.

알 수 없는 메시지, 잘못된 JSON, 유효하지 않은 상태 메시지는 기록하고 화면 메시지로 표시하되 GUI를 종료하지 않습니다.

## 테스트

```powershell
cd client
.\.venv\Scripts\python.exe -m unittest discover -v
```

15×15/19×19 생성과 좌표 round trip, JSON 처리, `joined`, `game_start`, `move_result`, authoritative `game_state`, `game_over`, 크기를 유지하는 `restart`, 알 수 없는 메시지 및 잘못된 상태의 원자적 거부를 테스트합니다. 실제 서버 연동은 서버 구현과 함께 두 클라이언트로 확인해야 합니다.
