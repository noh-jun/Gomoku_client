#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="${SCRIPT_DIR}"
BUILD_ROOT="${CLIENT_DIR}/build/macos"
BUILD_VENV="${BUILD_ROOT}/.venv"
BUILD_PYTHON="${BUILD_VENV}/bin/python"
DIST_DIR="${CLIENT_DIR}/dist/macos"
APP_BUNDLE="${DIST_DIR}/OmokClient.app"
ZIP_PATH="${DIST_DIR}/OmokClient.zip"
DMG_PATH="${DIST_DIR}/OmokClient.dmg"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "[ERROR] This script must be run on macOS." >&2
    exit 1
fi

if [[ ! -f "${CLIENT_DIR}/client.py" ]]; then
    echo "[ERROR] Client entry point was not found: ${CLIENT_DIR}/client.py" >&2
    exit 1
fi

if [[ ! -x "${BUILD_PYTHON}" ]]; then
    if ! command -v python3 >/dev/null 2>&1; then
        echo "[ERROR] Python 3.11 or newer is required." >&2
        exit 1
    fi

    if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
        echo "[ERROR] Python 3.11 or newer is required." >&2
        exit 1
    fi

    echo "[INFO] Creating the macOS client build environment..."
    python3 -m venv "${BUILD_VENV}"
fi

echo "[INFO] Installing client and build dependencies..."
"${BUILD_PYTHON}" -m pip install \
    -r "${CLIENT_DIR}/requirements.txt" \
    pyinstaller

echo "[INFO] Building OmokClient.app for $(uname -m)..."
"${BUILD_PYTHON}" -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --windowed \
    --name OmokClient \
    --distpath "${DIST_DIR}" \
    --workpath "${BUILD_ROOT}/work" \
    --specpath "${BUILD_ROOT}" \
    "${CLIENT_DIR}/client.py"

echo "[INFO] Verifying the bundle before packaging..."
codesign --verify --deep --strict "${APP_BUNDLE}"

echo "[INFO] Packaging the bundle for distribution..."
rm -f "${ZIP_PATH}" "${DMG_PATH}"

# ditto preserves the bundle's symlinks, POSIX permissions and extended
# attributes. Plain zip dereferences the symlinks and invalidates the code
# signature, which makes macOS reject the copy the recipient receives.
ditto -c -k --keepParent "${APP_BUNDLE}" "${ZIP_PATH}"

hdiutil create \
    -volname OmokClient \
    -srcfolder "${APP_BUNDLE}" \
    -ov \
    -format UDZO \
    -quiet \
    "${DMG_PATH}"

echo
echo "[SUCCESS] Application bundle created:"
echo "${APP_BUNDLE}"
echo
echo "[SUCCESS] Distributable archives created:"
echo "${DMG_PATH}"
echo "${ZIP_PATH}"
echo
echo "[NOTE] Send the .dmg or the .zip as a single file."
echo "       Uploading OmokClient.app itself to a file service stores it as a"
echo "       folder, which drops the bundle's symlinks and executable bits."
echo
echo "[NOTE] This build is ad-hoc signed, so macOS quarantines it on delivery."
echo "       Until it is signed with a Developer ID and notarized, the"
echo "       recipient has to clear the quarantine flag once:"
echo "         xattr -dr com.apple.quarantine /Applications/OmokClient.app"
