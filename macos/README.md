# macOS 앱 번들

오목 클라이언트를 터미널 없이 더블클릭으로 실행하기 위한 앱 번들 생성 스크립트입니다.

## 사전 준비

프로젝트 루트에 tkinter가 동작하는 가상환경이 있어야 합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

macOS 26 이상에서는 시스템 파이썬(3.9)의 Tk 8.5가 실행되지 않습니다
(`macOS 26 (2602) or later required`). Tk 8.6 이상이 포함된 파이썬을 쓰세요.
uv를 쓴다면 아래가 가장 간단합니다.

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt
```

## 번들 생성

```bash
bash macos/build_app.sh              # ~/Desktop/오목.app 생성
bash macos/build_app.sh /Applications/오목.app
```

스크립트는 아이콘 생성, 번들 구성, 애드혹 코드 서명, LaunchServices 등록까지 처리합니다.
프로젝트 절대 경로가 실행 스크립트에 구워지므로, 프로젝트 폴더를 옮기면 다시 실행하세요.

## 구성

| 파일 | 역할 |
| --- | --- |
| `build_app.sh` | 번들 생성 전체 절차 |
| `Info.plist` | 번들 메타데이터 템플릿 |
| `launch.py` | 창을 최전면으로 올리는 실행 진입점 |
| `make_icon.py` | 의존성 없이 아이콘 PNG 생성 |

`launch.py`는 `client.py`와 동작이 같지만, 번들에서 실행할 때 창이 다른 창 뒤나 다른
Space에 묻히지 않도록 생성 직후 `lift()`와 일시적인 topmost를 적용합니다.

## 문제 해결

실행이 안 되면 먼저 로그를 확인하세요.

```bash
cat ~/Library/Logs/omok-client.log
```

- `가상환경(.venv)이 없습니다` — 위의 사전 준비를 수행하세요.
- `이 파이썬에 tkinter가 없습니다` — Homebrew 파이썬이라면 `brew install python-tk@<버전>`이 필요합니다.
- 로그가 비어 있다면 macOS가 실행 자체를 막은 경우입니다. 앱을 우클릭 후 `열기`를 한 번
  선택하면 이후부터 더블클릭으로 실행됩니다.
