# Room 채팅 클라이언트 계약

- 채팅은 Room 단위의 단일 채널이다. 같은 Room의 Player와 Observer 전원이 같은 대화를 본다. Lobby 채팅은 없다.
- 클라이언트는 `{"type": "chat", "text": "..."}`를 전송한다.
- `text`는 앞뒤 공백을 제거한 뒤 1~200자여야 하며 제어문자와 줄 구분 문자를 포함할 수 없다. 클라이언트가 먼저 검증하고 서버도 같은 규칙으로 다시 검증한다.
- 서버는 검증을 통과한 메시지를 발신자를 포함한 Room 전원에게 `chat_message`로 브로드캐스트한다.

```json
{
  "type": "chat_message",
  "nickname": "홍길동",
  "text": "안녕하세요",
  "sent_at_unix_ms": 1725760000000
}
```

- `nickname`은 `room_members`와 같은 규칙(1~20자, NFKC)으로 정규화된 발신자 닉네임이다. 클라이언트는 `connection_id`나 `account_id`가 포함될 것으로 기대하지 않는다.
- `sent_at_unix_ms`는 서버 기준 수신 시각이다. 클라이언트는 이 값으로 `HH:MM`을 표시하며 자체 시계를 쓰지 않는다.
- 클라이언트는 자기 메시지를 로컬에 먼저 추가하지 않는다. 서버가 되돌려준 `chat_message`만 표시한다. 착수와 같은 원칙이다.
- 클라이언트는 `IN_ROOM` 상태에서만 `chat_message`를 수용하고 그 외에는 거부한다.
- 클라이언트는 최근 200건만 보관한다. `joined`, `left_room`, 연결 종료 시 대화를 비운다.
- 입장 시 서버는 과거 대화를 내려주지 않는다. 입장 이후 도착한 메시지만 본다.
- 채팅 입력은 Room 안이면 게임 상태(`WAITING`/`PLAYING`/`FINISHED`)와 역할에 관계없이 항상 사용할 수 있다.
- 표시는 Game 화면 오른쪽 열에서 사용자 목록 아래에 두며 `HH:MM 닉네임: 본문` 형식으로 최신 메시지가 아래에 온다.

## 오류

- `CHAT_NOT_AVAILABLE` — Room 밖이거나 인증되지 않은 상태에서 `chat`을 보낸 경우.
- `CHAT_TEXT_INVALID` — 길이·문자 규칙 위반.
- `CHAT_RATE_LIMITED` — 전송 빈도 초과. 서버 권장 한도는 사용자당 초당 2건이다.

오류는 기존 `error` 메시지 형식(`code`, `message`)으로 전달하며, 클라이언트는 문구만 표시하고 입력 내용은 지우지 않는다.
