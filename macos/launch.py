"""macOS 앱 번들 전용 런처.

`client.py`와 동작은 같지만, 번들에서 실행할 때 창이 다른 창 뒤나
다른 Space에 묻히지 않도록 생성 직후 최전면으로 올린 뒤 topmost를 해제한다.
프로젝트 경로는 번들 런처가 `OMOK_PROJECT` 환경변수로 전달한다.
"""

from __future__ import annotations

import logging
import os
import sys
import tkinter as tk

TOPMOST_RELEASE_MS = 500

PROJECT_PATH = os.environ.get("OMOK_PROJECT")
if not PROJECT_PATH:
    raise SystemExit("OMOK_PROJECT 환경변수가 필요합니다.")

sys.path.insert(0, PROJECT_PATH)

from omok_client.gui import OmokApp  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    root = tk.Tk()
    OmokApp(root)

    root.update_idletasks()
    root.lift()
    root.attributes("-topmost", True)
    root.after(TOPMOST_RELEASE_MS, lambda: root.attributes("-topmost", False))
    try:
        root.focus_force()
    except tk.TclError:
        LOGGER.debug("focus_force 실패, 무시합니다.")

    LOGGER.info("창 표시 완료: %s", root.winfo_geometry())
    root.mainloop()


if __name__ == "__main__":
    main()
