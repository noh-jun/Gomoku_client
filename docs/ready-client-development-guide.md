# Ready 클라이언트 처리 지침

## 목적

Room 입장만으로 게임은 시작되지 않는다. 최초 대국과 다음 대국 모두 두 플레이어가
`ready`를 전송한 뒤 시작한다. Ready는 기존 Restart UI와 프로토콜을 대체한다.

## 전송

Ready 버튼을 누르면 다음 메시지를 전송한다.

```json
{ "type": "ready" }
```

버튼은 자신의 역할이 Player이고 Player가 정확히 2명이며 `WAITING` 또는 `FINISHED`
상태일 때만 활성화한다. 전송 직후 서버 응답 전까지 중복 입력을 막는다.

## Ready 알림

```json
{
  "type": "player_ready",
  "color": "WHITE",
  "ready_count": 1,
  "required": 2
}
```

- 요청자는 `ready_confirmed`를 받은 뒤 `SystemBlockingOverlay`를 표시한다.
- 상대 Player는 `player_ready`를 받고 클릭으로 닫을 수 있는 `CanvasOverlay`를 표시한다.
- Observer에게는 Ready 알림이 전달되지 않는다.
- 두 경우 모두 바둑판 밖의 Room 퇴장과 연결 종료 버튼은 사용할 수 있다.

## 게임 시작

두 플레이어가 Ready하면 서버가 플레이어별 `game_start`와 공통 `game_state`를 보낸다.
`game_start.your_color`로 자신의 색상을 갱신하고 모든 Ready overlay와 Ready 상태를
초기화한다. 보드와 턴은 서버 메시지만 신뢰한다.

## 초기화

`joined`, `left_room`, `player_disconnected`, 연결 종료 및 `game_start`에서 Ready UI의
pending 상태와 overlay를 제거한다. `READY_NOT_AVAILABLE` 또는
`READY_REQUIRES_TWO_PLAYERS` 오류를 받으면 전송 pending만 해제하고 오류 문구를 표시한다.
