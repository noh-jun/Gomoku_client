# Room Player/Observer 클라이언트 처리

- Room에는 최대 99명이 입장하고 Player는 최대 2명이다.
- 모든 사용자는 `joined`에서 Observer로 시작한다.
- `Become Player`와 `Observe` 버튼으로 역할을 전환한다.
- 게임이 `PLAYING`이면 두 역할 전환 버튼을 비활성화한다.
- Player 2명이 확정된 경우에만 Player의 Ready 버튼을 활성화한다.
- Observer는 Ready, 착수, Undo를 사용할 수 없다.
- `room_members`의 인원과 `ready_colors`를 Room 표시의 기준으로 사용한다.
- `ready_confirmed`를 받은 Player는 상대 Ready 대기 overlay를 표시한다.
- `player_ready`는 상대 Player에게만 도착하며 Player Ready 안내를 표시한다.
- Observer도 `game_start`, `move_result`, `game_state`, `game_over`, `undo_result`를
  적용해 같은 보드를 관전한다.
- Observer의 `game_start`는 `your_color: null`이다.
