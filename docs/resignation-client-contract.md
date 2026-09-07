# 기권 클라이언트 계약

- In-Game 영역은 `[무르기] [기권]` 순서로 표시한다.
- `PLAYING` 상태의 Player만 기권 버튼을 사용할 수 있다.
- 첫 착수 전에도 기권할 수 있다.
- 확인 Action Overlay가 표시되는 동안에도 서버 Turn Timer는 계속 진행된다.
- 확인 후 `resign`을 전송하고 System Blocking Overlay로 결과를 기다린다.
- `game_over` 또는 오류를 받으면 기권 Overlay 상태를 제거한다.
- `RESIGNATION` 결과는 기권자, 승자 및 Observer에게 구분되는 문구로 표시한다.
