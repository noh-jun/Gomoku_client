# Room Name 클라이언트-서버 송수신 계약

## 목적

클라이언트의 `Create Room` 모달에서 사용자가 입력한 방 이름을 서버가 저장하고 Lobby의 모든 클라이언트에 동일하게 제공하기 위한 WebSocket 계약입니다.

이 계약은 현재 서버 구현에 반영되어 있습니다. 신규 클라이언트는 아래의 `room_name`
필드를 필수 필드로 취급해야 합니다.

`room_id`와 `room_name`은 역할이 다릅니다.

- `room_id`: 서버가 생성하는 불변·고유 식별자입니다. `join_room`, 내부 Room 조회, 게임 세션 연결에 사용합니다.
- `room_name`: 사용자가 입력하는 표시 이름입니다. Lobby 카드와 Game 화면에 표시합니다.

방 이름을 Room 식별자로 사용하면 중복 이름, Unicode 표기 차이, 향후 이름 변경 때문에 세션 조회가 불안정해지므로 반드시 두 필드를 분리합니다. 현재 범위에서는 방 이름 변경 기능을 제공하지 않습니다.

## 방 이름 정규화 및 검증

서버가 최종 권한을 가지며 다음 순서로 검증해야 합니다.

1. JSON의 `room_name`이 문자열인지 확인합니다.
2. Unicode NFKC 정규화를 적용합니다.
3. 문자열 양 끝의 공백을 제거합니다. 내부 공백은 유지합니다.
4. 정규화된 길이가 1~30 Unicode 문자(code point)인지 확인합니다.
5. Unicode 범주 `Cc`, `Cs`, `Zl`, `Zp`에 해당하는 제어 문자·서로게이트·줄 구분 문자를 거부합니다.
6. 중복 비교 키는 `normalized_room_name.casefold()`로 계산합니다.

서버는 정규화된 표시 이름을 저장하고 응답에도 그 값을 사용해야 합니다. 중복 검사와 Room 등록은 하나의 임계 구역 또는 단일 이벤트 루프 작업에서 원자적으로 처리하여 동시 생성 경쟁을 막아야 합니다.

## Client → Server

### 방 생성

```json
{
  "type": "create_room",
  "room_name": "친선 대국"
}
```

클라이언트는 `board_size`, `win_length`, `room_id`를 보내지 않습니다. 보드 설정과 `room_id` 생성은 서버 책임입니다.

### 방 입장

방 이름이 아니라 불변 ID를 사용합니다.

```json
{
  "type": "join_room",
  "room_id": "room_001"
}
```

## Server → Client

### 생성 확인

```json
{
  "type": "room_created",
  "room_id": "room_001",
  "room_name": "친선 대국"
}
```

생성자는 생성 직후 해당 방에 자동 입장합니다. 서버는 `room_created` 다음에 기존 입장 계약의 `joined`를 전송해야 합니다. 클라이언트는 `joined`를 받아야 Lobby에서 Game 화면으로 전환합니다.

```json
{
  "type": "joined",
  "room_id": "room_001",
  "room_name": "친선 대국",
  "your_color": "WHITE",
  "board_size": 15,
  "win_length": 5,
  "starting_color": "WHITE"
}
```

### Room 목록

`room_list.rooms[]`의 각 항목에 `room_name`을 필수로 포함합니다.

```json
{
  "type": "room_list",
  "rooms": [
    {
      "room_id": "room_001",
      "room_name": "친선 대국",
      "board_size": 15,
      "win_length": 5,
      "players": 1,
      "max_players": 2,
      "status": "WAITING"
    }
  ]
}
```

Room 생성·입장·퇴장·disconnect, 게임 시작·종료·Restart로 상태가 변경되면 서버는
Lobby 클라이언트에 최신 `room_list` 스냅샷을 전송합니다. `get_room_list` 요청에도
같은 최신 스냅샷을 반환합니다.

## 클라이언트 수신 처리 계약

클라이언트는 자신이 전송한 원본 문자열이 아니라 서버 응답의 정규화된 `room_name`을
화면과 상태의 기준으로 사용해야 합니다.

| 메시지 | 수신 대상 | `room_name` 처리 |
|---|---|---|
| `room_created` | 생성 요청자 | 생성된 ID와 정규화된 이름을 확인하되 아직 Game 화면으로 전환하지 않음 |
| `joined` | 생성자 또는 입장자 | `room_id`와 `room_name`을 현재 Room 상태로 저장하고 Game 화면으로 전환 |
| `room_list` | Lobby 연결 | 각 항목의 `room_name`을 Room 카드 표시 이름으로 사용하고 목록 snapshot을 교체 |

### 생성 요청의 정상 수신 순서

```text
Client → create_room(room_name)
Client ← room_created(room_id, normalized room_name)
Client ← joined(room_id, normalized room_name, your_color, settings)
Lobby clients ← room_list(... normalized room_name ...)
```

`room_created`는 생성 확인 메시지이고, 실제 Room 입장 확정 메시지는 `joined`입니다.
클라이언트는 `room_created`만 받고 Game 화면으로 이동하면 안 됩니다.

### 기존 Room 입장의 정상 수신 순서

```text
Client → join_room(room_id)
Client ← joined(room_id, room_name, your_color, settings)
Room players ← game_start / game_state
Lobby clients ← room_list
```

`join_room` 요청에는 `room_name`을 보내지 않습니다. 서버가 Room ID로 조회한 저장 이름을
`joined.room_name`에 담아 돌려주며, 클라이언트는 이 값을 현재 Game 화면에 표시합니다.

### Room List 항목의 필수 필드

신규 서버와 신규 클라이언트 사이에서는 다음 필드를 모두 필수로 취급합니다.

- `room_id`: 입장 요청과 선택 유지에 사용하는 불변 식별자
- `room_name`: Lobby와 Game 화면에 표시할 서버 정규화 이름
- `board_size`
- `win_length`
- `players`
- `max_players`
- `status`: `WAITING`, `PLAYING`, `FINISHED`

동일한 `room_id`의 새 snapshot이 도착하면 이름을 포함한 해당 항목 전체를 최신 값으로
교체합니다. Room List에서 사라진 ID는 삭제된 방으로 처리합니다.

## 오류 응답

모든 실패는 Room을 만들거나 사용자를 입장시키지 않은 상태에서 다음 형식으로 반환합니다.

```json
{
  "type": "error",
  "code": "ROOM_NAME_TAKEN",
  "message": "A room with that name already exists."
}
```

서버가 반환하는 Room Name 관련 오류 코드는 다음과 같습니다.

- `INVALID_ROOM_NAME`: 누락, 타입 오류, 빈 문자열, 길이 초과, 금지 문자
- `ROOM_NAME_TAKEN`: NFKC 정규화 및 `casefold()` 기준으로 같은 이름이 이미 존재함
- `ALREADY_IN_ROOM`: 생성 요청자가 이미 Room에 입장한 상태
- `CREATE_ROOM_FAILED`: 예상하지 못한 서버 내부 실패

클라이언트는 오류를 받으면 생성 대기 상태를 해제하고 Lobby에 남습니다. 서버 내부 오류의 상세 정보나 스택 트레이스는 `message`에 포함하지 않습니다.

## 서버 처리 순서

1. WebSocket 세션이 Lobby 상태인지 확인합니다.
2. `room_name`을 정규화하고 검증합니다.
3. 중복 이름 검사, `room_id` 생성, Room 등록을 원자적으로 수행합니다.
4. 생성자를 Room 멤버로 등록하고 색상을 배정합니다.
5. 생성자에게 `room_created`와 `joined`를 순서대로 전송합니다.
6. 다른 Lobby 세션에 갱신된 `room_list`를 전파합니다.
7. 중간 단계에서 실패하면 부분 생성된 Room과 멤버십을 롤백하고 `error`를 반환합니다.

## 구현 및 호환성 참고

- 현재 서버는 `room_created`, `joined`, `room_list.rooms[]`에 정규화된
  `room_name`을 항상 포함합니다.
- 현재 클라이언트에는 구버전 서버 전환을 위한 `room_id` 표시 fallback이 남아 있지만,
  신규 연동의 정상 계약으로 사용하지 않습니다.
- 서버의 현재 Room ID 형식은 `room_001`, `room_002`와 같은 순차 ID입니다. 클라이언트는
  형식을 파싱하지 말고 불투명한 문자열로 보관하고 다시 전송해야 합니다.
- 현재 서버의 기본 첫 번째 플레이어와 선공 색상은 WHITE입니다. 클라이언트는 고정값을
  추정하지 말고 `joined.your_color`와 `joined.starting_color`를 사용해야 합니다.
