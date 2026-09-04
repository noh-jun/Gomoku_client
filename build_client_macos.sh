#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="${SCRIPT_DIR}"
BUILD_ROOT="${CLIENT_DIR}/build/macos"
BUILD_VENV="${BUILD_ROOT}/.venv"
BUILD_PYTHON="${BUILD_VENV}/bin/python"
DIST_DIR="${CLIENT_DIR}/dist/macos"

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

echo
echo "[SUCCESS] Application bundle created:"
echo "${DIST_DIR}/OmokClient.app"
