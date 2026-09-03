import logging
import tkinter as tk

from .gui import OmokApp


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    root = tk.Tk()
    OmokApp(root)
    root.mainloop()

