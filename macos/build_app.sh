#!/bin/bash
# 오목 클라이언트를 더블클릭으로 실행할 수 있는 macOS 앱 번들을 만든다.
#
#   사용법: bash macos/build_app.sh [설치 경로]
#   기본 설치 경로: ~/Desktop/오목.app
#
# 워크트리에서 빌드하면서 실행 대상은 다른 체크아웃으로 두고 싶다면
# OMOK_PROJECT_ROOT 로 프로젝트 경로를 지정한다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${OMOK_PROJECT_ROOT:-$SCRIPT_DIR/..}" && pwd)"
APP_PATH="${1:-$HOME/Desktop/오목.app}"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

if [ "$(uname -s)" != "Darwin" ]; then
  echo "이 스크립트는 macOS 전용입니다." >&2
  exit 1
fi

# 아이콘 생성에 쓸 파이썬을 고른다. 표준 라이브러리만 쓰므로 아무 파이썬이나 된다.
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "python3를 찾을 수 없습니다." >&2
  exit 1
fi

echo "프로젝트: $REPO_ROOT"
echo "설치 경로: $APP_PATH"

# 1) 아이콘 생성 (PNG -> iconset -> icns)
"$PYTHON" "$SCRIPT_DIR/make_icon.py" "$BUILD_DIR/omok.png"

ICONSET="$BUILD_DIR/omok.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$BUILD_DIR/omok.png" \
    --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  retina=$((size * 2))
  sips -z "$retina" "$retina" "$BUILD_DIR/omok.png" \
    --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$BUILD_DIR/omok.icns"

# 2) 번들 구성
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Resources"
cp "$SCRIPT_DIR/Info.plist" "$APP_PATH/Contents/Info.plist"
cp "$SCRIPT_DIR/launch.py" "$APP_PATH/Contents/Resources/launch.py"
cp "$BUILD_DIR/omok.icns" "$APP_PATH/Contents/Resources/omok.icns"

# 3) 실행 스크립트 (프로젝트 절대 경로를 굽는다)
cat > "$APP_PATH/Contents/MacOS/omok" <<EOF
#!/bin/bash
# macos/build_app.sh 가 생성한 파일입니다. 직접 수정하지 마세요.

PROJECT="$REPO_ROOT"
LOG="\$HOME/Library/Logs/omok-client.log"
BUNDLE_RES="\$(cd "\$(dirname "\$0")/../Resources" && pwd)"

mkdir -p "\$(dirname "\$LOG")"
exec >>"\$LOG" 2>&1
echo "=== \$(date '+%Y-%m-%d %H:%M:%S') 실행 시도 ==="

fail() {
  echo "실패: \$1"
  osascript -e "display alert \"오목 실행 실패\" message \"\$1\"" >/dev/null 2>&1
  exit 1
}

cd "\$PROJECT" || fail "프로젝트 폴더를 찾을 수 없습니다: \$PROJECT"

PY="\$PROJECT/.venv/bin/python"
[ -x "\$PY" ] || fail "가상환경(.venv)이 없습니다. 프로젝트 폴더에서 다시 구성해 주세요."

"\$PY" -c "import tkinter" 2>/dev/null || fail "이 파이썬에 tkinter가 없습니다."

echo "python=\$PY"
export OMOK_PROJECT="\$PROJECT"
exec "\$PY" "\$BUNDLE_RES/launch.py"
EOF
chmod +x "$APP_PATH/Contents/MacOS/omok"

# 4) 애드혹 서명과 LaunchServices 등록
codesign --force --deep --sign - "$APP_PATH" >/dev/null 2>&1 || \
  echo "경고: 코드 서명에 실패했습니다. 실행에는 보통 문제가 없습니다." >&2

LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP_PATH" || true

echo "완료: $APP_PATH"
echo "실행 로그: ~/Library/Logs/omok-client.log"
