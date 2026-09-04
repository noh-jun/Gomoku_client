# Room Name 서버 구현 계약

## 목적

클라이언트의 `Create Room` 모달에서 사용자가 입력한 방 이름을 서버가 저장하고 Lobby의 모든 클라이언트에 동일하게 제공하기 위한 WebSocket 계약입니다.

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
  "room_id": "room_01J8XYZ"
}
```

## Server → Client

### 생성 확인

```json
{
  "type": "room_created",
  "room_id": "room_01J8XYZ",
  "room_name": "친선 대국"
}
```

생성자는 생성 직후 해당 방에 자동 입장합니다. 서버는 `room_created` 다음에 기존 입장 계약의 `joined`를 전송해야 합니다. 클라이언트는 `joined`를 받아야 Lobby에서 Game 화면으로 전환합니다.

```json
{
  "type": "joined",
  "room_id": "room_01J8XYZ",
  "room_name": "친선 대국",
  "your_color": "BLACK",
  "board_size": 15,
  "win_length": 5,
  "starting_color": "BLACK"
}
```

### Room 목록

`room_list.rooms[]`의 각 항목에 `room_name`을 필수로 포함합니다.

```json
{
  "type": "room_list",
  "rooms": [
    {
      "room_id": "room_01J8XYZ",
      "room_name": "친선 대국",
      "board_size": 15,
      "players": 1,
      "max_players": 2,
      "status": "WAITING"
    }
  ]
}
```

Room 생성·입장·퇴장 또는 상태 변경 후에는 Lobby 클라이언트에 최신 `room_list` 스냅샷을 전송하거나, 적어도 `get_room_list` 요청에 최신 스냅샷을 반환해야 합니다.

## 오류 응답

모든 실패는 Room을 만들거나 사용자를 입장시키지 않은 상태에서 다음 형식으로 반환합니다.

```json
{
  "type": "error",
  "code": "ROOM_NAME_TAKEN",
  "message": "A room with that name already exists."
}
```

권장 오류 코드는 다음과 같습니다.

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

## 호환성 참고

현재 클라이언트는 이전 서버와의 전환 기간을 위해 Server 응답에 `room_name`이 없으면 표시 이름으로 `room_id`를 사용합니다. 신규 서버 구현은 이 fallback에 의존하지 말고 `room_created`, `joined`, `room_list.rooms[]`에 항상 `room_name`을 포함해야 합니다.
