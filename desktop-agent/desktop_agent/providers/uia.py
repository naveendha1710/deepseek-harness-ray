from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pywinauto import Desktop


class UIAError(RuntimeError):
    """Raised when a UI Automation operation fails."""


@dataclass(frozen=True)
class WindowInfo:
    title: str
    rect: tuple[int, int, int, int] | None
    pid: int
    visible: bool
    enabled: bool


@dataclass(frozen=True)
class WindowCandidate:
    """Metadata for one visible top-level UIA window candidate."""

    title: str
    pid: int
    handle: int
    rect: tuple[int, int, int, int] | None
    visible: bool
    enabled: bool
    class_name: str | None = None
    framework_id: str | None = None


class UIAAdapter:
    """Primary UI Automation layer for Windows UIA-only flows."""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self.desktop = Desktop(backend="uia")

    def window_spec(self, title_re: str):
        """Return a specification only when exactly one window matches."""

        try:
            candidates = self.list_window_candidates(title_re)
            candidate = self._select_candidate(candidates, title_re=title_re)
            return self.window_spec_by_handle(candidate.handle)
        except UIAError:
            raise
        except Exception as exc:
            raise UIAError(
                f"Window lookup failed: title_re={title_re!r}: {exc}"
            ) from exc

    def window_spec_by_pid(self, pid: int, title_re: str | None = None):
        """Return a specification when PID plus an optional title is unique."""

        selector = ".*" if title_re is None else title_re
        try:
            candidates = [
                candidate
                for candidate in self.list_window_candidates(selector)
                if candidate.pid == pid
            ]
            candidate = self._select_candidate(
                candidates, selector_name=f"pid={pid} title_re={title_re!r}"
            )
            return self.window_spec_by_handle(candidate.handle)
        except UIAError:
            raise
        except Exception as exc:
            raise UIAError(
                f"PID window lookup failed: pid={pid} title_re={title_re!r}: {exc}"
            ) from exc

    def window_spec_by_handle(self, handle: int):
        """Return a top-level WindowSpecification resolved by native handle."""

        try:
            spec = self.desktop.window(handle=handle)
            if not spec.exists(timeout=self.timeout):
                raise UIAError(f"Window not found: handle={handle}")
            return spec
        except UIAError:
            raise
        except Exception as exc:
            raise UIAError(
                f"Handle window lookup failed: handle={handle}: {exc}"
            ) from exc

    @classmethod
    def _select_candidate(
        cls,
        candidates: list[WindowCandidate],
        *,
        title_re: str | None = None,
        selector_name: str | None = None,
    ) -> WindowCandidate:
        """Select exactly one candidate and report zero or ambiguous matches."""

        if selector_name is None:
            selector_name = f"title_re={title_re!r}"
        if not candidates:
            raise UIAError(f"No window matched {selector_name}")
        if len(candidates) > 1:
            details = "; ".join(cls._candidate_description(c) for c in candidates)
            raise UIAError(
                f"Ambiguous window selector: {selector_name} matched "
                f"{len(candidates)} windows: {details}"
            )
        return candidates[0]

    def find_window(self, title_re: str):
        """Return the wrapped top-level window."""

        try:
            return self.window_spec(title_re).wrapper_object()
        except UIAError:
            raise
        except Exception as exc:
            raise UIAError(
                f"Window wrap failed: title_re={title_re!r}: {exc}"
            ) from exc

    def list_windows(self, title_re: str):
        """Return visible top-level UIA windows matching the title regex."""

        try:
            return self.desktop.windows(title_re=title_re, visible_only=True)
        except Exception as exc:
            raise UIAError(
                f"Window listing failed: title_re={title_re!r}: {exc}"
            ) from exc

    def list_window_candidates(self, title_re: str) -> list[WindowCandidate]:
        """Return metadata needed to select one visible window deterministically."""

        try:
            return [self._candidate_from_window(window) for window in self.list_windows(title_re)]
        except UIAError:
            raise
        except Exception as exc:
            raise UIAError(
                f"Window candidate listing failed: title_re={title_re!r}: {exc}"
            ) from exc

    @staticmethod
    def _candidate_from_window(window) -> WindowCandidate:
        rect = None
        try:
            bounds = window.rectangle()
            candidate_rect = (bounds.left, bounds.top, bounds.right, bounds.bottom)
            if candidate_rect != (0, 0, 0, 0):
                rect = candidate_rect
        except Exception:
            rect = None

        handle = getattr(window.element_info, "handle", 0)
        if not handle:
            raise UIAError(f"UIA window has no native handle: {window.window_text()!r}")
        return WindowCandidate(
            title=window.window_text(),
            pid=window.process_id(),
            handle=handle,
            rect=rect,
            visible=window.is_visible(),
            enabled=window.is_enabled(),
            class_name=UIAAdapter._optional_element_info_attr(
                window.element_info, "class_name"
            ),
            framework_id=UIAAdapter._optional_element_info_attr(
                window.element_info, "framework_id"
            ),
        )

    @staticmethod
    def _optional_element_info_attr(element_info, name: str):
        try:
            return getattr(element_info, name, None)
        except Exception:
            return None

    @staticmethod
    def _candidate_description(candidate: WindowCandidate) -> str:
        return (
            f"title={candidate.title!r}, pid={candidate.pid}, "
            f"handle={candidate.handle}, rect={candidate.rect}, "
            f"visible={candidate.visible}, enabled={candidate.enabled}"
        )

    def inspect_window(self, title_re: str) -> WindowInfo:
        """Collect stable metadata for a matching top-level window."""

        window = self.find_window(title_re)

        rect = None
        try:
            bounds = window.rectangle()
            candidate = (
                bounds.left,
                bounds.top,
                bounds.right,
                bounds.bottom,
            )
            if candidate != (0, 0, 0, 0):
                rect = candidate
        except Exception:
            rect = None

        return WindowInfo(
            title=window.window_text(),
            rect=rect,
            pid=window.process_id(),
            visible=window.is_visible(),
            enabled=window.is_enabled(),
        )

    def find_control(
        self,
        window_spec,
        *,
        title: str | None = None,
        name: str | None = None,
        auto_id: str | None = None,
        control_type: str | None = None,
    ):
        """Find a child control from a WindowSpecification."""

        criteria: dict[str, Any] = {}
        description: dict[str, Any] = {}
        if title is not None:
            criteria["title"] = title
            description["title"] = title
        if name is not None:
            # pywinauto's UIA title filter also checks rich_text. Match Name directly.
            criteria["predicate_func"] = lambda element_info: element_info.name == name
            description["name"] = name
        if auto_id is not None:
            criteria["auto_id"] = auto_id
            description["auto_id"] = auto_id
        if control_type is not None:
            criteria["control_type"] = control_type
            description["control_type"] = control_type
        if not criteria:
            raise ValueError("At least one control selector is required")

        try:
            control = window_spec.child_window(**criteria)
            if not control.exists(timeout=self.timeout):
                raise UIAError(f"Control not found: {description}")
            return control.wrapper_object()
        except UIAError:
            raise
        except Exception as exc:
            raise UIAError(
                f"Control lookup failed: {description}: {exc}"
            ) from exc

    def focus(self, control) -> None:
        """Set keyboard focus to a UIA control."""

        try:
            control.set_focus()
        except Exception as exc:
            raise UIAError(f"UIA focus failed: {exc}") from exc

    def click(self, control) -> None:
        """Focus and click a UIA control."""

        self.focus(control)
        try:
            control.click_input()
        except Exception as exc:
            raise UIAError(f"UIA click failed: {exc}") from exc

    def type_text(self, control, text: str) -> None:
        """Focus a control and type literal text into it."""

        self.focus(control)
        try:
            control.type_keys(text, with_spaces=True)
        except Exception as exc:
            raise UIAError(f"UIA typing failed: {exc}") from exc

    def press(self, control, keys: str) -> None:
        """Focus a control and send a pywinauto key sequence."""

        self.focus(control)
        try:
            control.type_keys(keys)
        except Exception as exc:
            raise UIAError(f"UIA keypress failed: {exc}") from exc

    def read_text_pattern(self, control) -> str:
        """Read the UIA Text Pattern from a control."""

        iface = getattr(control, "iface_text", None)
        if iface is None:
            raise UIAError("Control does not expose UIA Text Pattern")

        try:
            return iface.DocumentRange.GetText(-1)
        except Exception as exc:
            raise UIAError(f"UIA Text Pattern read failed: {exc}") from exc

    def inspect_controls(self, window_spec) -> None:
        """Print the UIA control tree for a matched window."""

        try:
            window_spec.print_control_identifiers()
        except Exception as exc:
            raise UIAError(f"Control inspection failed: {exc}") from exc
