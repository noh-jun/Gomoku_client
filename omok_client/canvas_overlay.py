from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Callable


@dataclass(frozen=True)
class OverlayOptions:
    """Content and behavior for a modal message drawn over a Canvas."""

    title: str
    message: str
    kind: str = "info"
    dismiss_on_click: bool = True
    dismiss_hint: str = "클릭하면 닫힙니다"
    content_tag: str | None = None


@dataclass(frozen=True)
class OverlayAction:
    """One explicit user decision rendered by :class:`ActionModalOverlay`."""

    label: str
    command: Callable[[], None]


@dataclass(frozen=True)
class _OverlayStyle:
    panel_fill: str
    panel_outline: str
    title_fill: str
    message_fill: str


_STYLES = {
    "info": _OverlayStyle("#FFF8EA", "#7B542B", "#3E2B18", "#3E2B18"),
    "warning": _OverlayStyle("#FFF3E0", "#C62828", "#9B1C1C", "#5A2018"),
    "error": _OverlayStyle("#FFEBEE", "#B71C1C", "#8E0000", "#5A1010"),
    "result": _OverlayStyle("#F8E8C8", "#7B542B", "#5A2018", "#5A2018"),
}


class CanvasOverlay:
    """Reusable, click-consuming modal message overlay for a Tk Canvas.

    The component owns only presentation state. Callers decide when an overlay
    should be shown and what dismissing it means to application state.
    """

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self._tag = f"canvas_overlay_{id(self)}"
        self._options: OverlayOptions | None = None
        self._on_dismiss: Callable[[], None] | None = None

    @property
    def visible(self) -> bool:
        return self._options is not None

    @property
    def kind(self) -> str | None:
        return self._options.kind if self._options is not None else None

    def show(
        self,
        options: OverlayOptions,
        on_dismiss: Callable[[], None] | None = None,
    ) -> None:
        self._options = options
        self._on_dismiss = on_dismiss
        self.redraw()

    def dismiss(self) -> None:
        callback = self._on_dismiss
        self.clear()
        if callback is not None:
            callback()

    def clear(self) -> None:
        """Remove the overlay without treating replacement/reset as a user dismissal."""
        self._options = None
        self._on_dismiss = None
        self.canvas.delete(self._tag)

    def consume_click(self) -> bool:
        """Consume a Canvas click while visible, dismissing when configured."""
        if self._options is None:
            return False
        if self._options.dismiss_on_click:
            self.dismiss()
        return True

    def redraw(self) -> None:
        self.canvas.delete(self._tag)
        options = self._options
        if options is None:
            return

        width = max(float(self.canvas.winfo_width()), 1.0)
        height = max(float(self.canvas.winfo_height()), 1.0)
        center_x = width / 2.0
        center_y = height / 2.0
        panel_width = min(640.0, max(320.0, width * 0.78))
        panel_height = min(230.0, max(170.0, height * 0.28))
        left = center_x - panel_width / 2.0
        top = center_y - panel_height / 2.0
        right = center_x + panel_width / 2.0
        bottom = center_y + panel_height / 2.0
        style = _STYLES.get(options.kind, _STYLES["info"])
        content_tags = (self._tag, "canvas_overlay")
        if options.content_tag:
            content_tags += (options.content_tag,)
        title_size = min(28, max(18, int(min(width, height) * 0.035)))
        message_size = min(36, max(20, int(min(width, height) * 0.045)))

        self.canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill="#29231D",
            stipple="gray50",
            outline="",
            tags=(self._tag, "canvas_overlay", "canvas_overlay_backdrop"),
        )
        self.canvas.create_rectangle(
            left,
            top,
            right,
            bottom,
            fill=style.panel_fill,
            outline=style.panel_outline,
            width=3,
            tags=content_tags + ("canvas_overlay_panel",),
        )
        self.canvas.create_text(
            center_x,
            top + 40,
            text=options.title,
            fill=style.title_fill,
            font=("TkDefaultFont", title_size, "bold"),
            width=panel_width - 40,
            justify="center",
            tags=(self._tag, "canvas_overlay", "canvas_overlay_title"),
        )
        self.canvas.create_text(
            center_x,
            center_y + 5,
            text=options.message,
            fill=style.message_fill,
            font=("TkDefaultFont", message_size, "bold"),
            width=panel_width - 44,
            justify="center",
            tags=content_tags + ("canvas_overlay_message",),
        )
        if options.dismiss_on_click and options.dismiss_hint:
            self.canvas.create_text(
                center_x,
                bottom - 24,
                text=options.dismiss_hint,
                fill="#76685A",
                font=("TkDefaultFont", 9),
                tags=(self._tag, "canvas_overlay", "canvas_overlay_hint"),
            )
        self.canvas.tag_raise(self._tag)


class ActionModalOverlay(CanvasOverlay):
    """Modal Canvas overlay whose sole responsibility is user decisions.

    Background clicks are consumed and never dismiss the modal.  The owning
    controller decides what each action means and when the overlay is cleared.
    """

    def __init__(self, canvas: tk.Canvas) -> None:
        super().__init__(canvas)
        self._action_buttons: list[ttk.Button] = []
        self._actions: tuple[OverlayAction, ...] = ()

    def show_actions(
        self,
        title: str,
        message: str,
        actions: tuple[OverlayAction, ...],
        kind: str = "info",
        content_tag: str | None = None,
    ) -> None:
        """Show a non-dismissible modal containing explicit action buttons."""
        if not actions:
            raise ValueError("ActionModalOverlay requires at least one action.")
        if any(not action.label.strip() for action in actions):
            raise ValueError("Overlay action labels must not be empty.")
        self._actions = actions
        super().show(
            OverlayOptions(
                title=title,
                message=message,
                kind=kind,
                dismiss_on_click=False,
                dismiss_hint="",
                content_tag=content_tag,
            )
        )

    def clear(self) -> None:
        self._destroy_action_buttons()
        self._actions = ()
        super().clear()

    def redraw(self) -> None:
        self._destroy_action_buttons()
        super().redraw()
        if not self.visible or not self._actions:
            return

        width = max(float(self.canvas.winfo_width()), 1.0)
        height = max(float(self.canvas.winfo_height()), 1.0)
        center_x = width / 2.0
        center_y = height / 2.0
        panel_width = min(640.0, max(320.0, width * 0.78))
        panel_height = min(230.0, max(170.0, height * 0.28))
        button_y = center_y + panel_height / 2.0 - 32.0
        gap = min(130.0, max(92.0, panel_width / max(len(self._actions), 2)))
        first_x = center_x - gap * (len(self._actions) - 1) / 2.0

        for index, action in enumerate(self._actions):
            button = ttk.Button(
                self.canvas,
                text=action.label,
                command=action.command,
            )
            self._action_buttons.append(button)
            self.canvas.create_window(
                first_x + gap * index,
                button_y,
                window=button,
                width=min(116.0, gap - 10.0),
                tags=(self._tag, "canvas_overlay", "action_modal_button"),
            )
        self.canvas.tag_raise(self._tag)

    def set_actions_enabled(self, enabled: bool) -> None:
        """Enable or disable every decision while a response is in flight."""
        state = "normal" if enabled else "disabled"
        for button in self._action_buttons:
            button.configure(state=state)

    def _destroy_action_buttons(self) -> None:
        for button in self._action_buttons:
            button.destroy()
        self._action_buttons.clear()


class SystemBlockingOverlay(CanvasOverlay):
    """Non-interactive modal removed only by an application state transition."""

    def show_blocking(
        self,
        title: str,
        message: str,
        kind: str = "info",
        content_tag: str | None = None,
    ) -> None:
        """Block Canvas input without exposing a user-dismiss path."""
        super().show(
            OverlayOptions(
                title=title,
                message=message,
                kind=kind,
                dismiss_on_click=False,
                dismiss_hint="",
                content_tag=content_tag,
            )
        )

    def dismiss(self) -> None:
        """Ignore user-style dismiss requests; the controller must clear it."""

    def clear_from_system(self) -> None:
        """Remove the blocker after a server or application state transition."""
        super().clear()
