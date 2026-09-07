# Room 사용자 목록 클라이언트 계약

- Connection 화면에서 1~20자의 닉네임을 입력한다.
- WebSocket 연결 직후 `set_nickname`을 전송하고 `nickname_confirmed`를 기다린다.
- 닉네임 확인 전에는 Room 생성과 입장을 비활성화한다.
- 닉네임은 NFKC 정규화하고 앞뒤 공백, 제어문자 및 줄 구분 문자를 검증한다.
- 중복 닉네임은 서로 다른 사용자로 그대로 표시하며 병합하지 않는다.
- `room_members.player_list`와 `observer_list`는 매번 전체 snapshot으로 교체한다.
- Player 목록에는 닉네임, 색상, Ready 상태를 표시한다.
- Observer 목록에는 닉네임을 입장 순서대로 표시한다.
- Room 퇴장 또는 연결 종료 시 목록을 비운다.

클라이언트는 사용자 목록에 내부 `connection_id`가 포함될 것으로 기대하지 않는다.
