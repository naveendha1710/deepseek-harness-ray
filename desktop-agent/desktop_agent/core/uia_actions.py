from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable

from desktop_agent.providers.uia import UIAAdapter, UIAError


class CapabilityStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    SUPPORTED_BUT_PATTERN_UNAVAILABLE = "SUPPORTED_BUT_PATTERN_UNAVAILABLE"
    CONTROL_NOT_EXPOSED = "CONTROL_NOT_EXPOSED"
    ACTION_FAILED = "ACTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class ActionResult:
    control: str
    primitive: str
    status: CapabilityStatus
    before: Any = None
    action: str | None = None
    after: Any = None
    expected: Any = None
    verification: str = "NOT_RUN"
    error: str | None = None
    elapsed_seconds: float = 0.0
    control_metadata: dict[str, Any] | None = None
    diagnostic: dict[str, Any] | None = None


@dataclass
class RepeatabilityResult:
    operation: str
    repetitions: int
    passed: int
    failed: int
    results: list[ActionResult] = field(default_factory=list)


@dataclass
class ActionReport:
    fixture: dict[str, Any]
    controls: list[dict[str, Any]]
    actions: list[ActionResult]
    repeatability: list[RepeatabilityResult]
    failures: list[str]
    timings: dict[str, float]


def verify_expected(actual: Any, expected: Any) -> bool:
    return actual == expected


def _pattern(control: Any, name: str) -> Any:
    try:
        pattern = getattr(control, name, None)
    except Exception:
        return None
    return pattern


def _value(pattern: Any, name: str) -> Any:
    try:
        return getattr(pattern, name)
    except Exception:
        return None


def _focus_state(control: Any) -> Any:
    try:
        return control.element_info._element.CurrentHasKeyboardFocus
    except Exception:
        return None


def verify_focus_state(control: Any, wait_seconds: float = 0.25) -> dict[str, Any]:
    """Read UIA keyboard focus immediately and after a bounded wait."""
    before = _focus_state(control)
    started = time.monotonic()
    immediate = _focus_state(control)
    if immediate is not True and immediate != 1 and wait_seconds > 0:
        time.sleep(wait_seconds)
    final = _focus_state(control)
    if final is None:
        result = "FOCUS_STATE_UNVERIFIABLE"
    elif final is True or final == 1:
        result = "VERIFIED"
    else:
        result = "FAILED"
    return {
        "control_identity": _control_metadata(control),
        "focus_state_before": before,
        "focus_state_immediate": immediate,
        "focus_state_after_wait": final,
        "verification_method": "IUIAutomationElement.CurrentHasKeyboardFocus",
        "wait_seconds": time.monotonic() - started,
        "result": result,
    }


def _control_metadata(control: Any) -> dict[str, Any]:
    info = control.element_info
    return {
        "name": _value(info, "name"),
        "control_type": _value(info, "control_type"),
        "auto_id": _value(info, "automation_id"),
        "class_name": _value(info, "class_name"),
        "framework_id": _value(info, "framework_id"),
        "pid": _value(info, "process_id"),
        "handle": _value(info, "handle"),
        "runtime_id": list(_value(info, "runtime_id") or []),
        "visible": _value(info, "visible"),
        "enabled": _value(info, "enabled"),
    }


class D3CActionProbe:
    """Execute controlled semantic UIA actions against the D3C fixture."""

    def __init__(self, adapter: UIAAdapter, window_spec: Any):
        self.adapter = adapter
        self.window_spec = window_spec
        self.last_lookup_error: str | None = None

    def control(self, name: str, control_type: str):
        return self.adapter.find_control(
            self.window_spec, name=name, control_type=control_type
        )

    def invoke(self, control_name: str, control_type: str = "Button") -> ActionResult:
        control = self._find(control_name, control_type)
        if control is None:
            return self._missing(control_name, "InvokePattern", self.last_lookup_error)
        pattern = _pattern(control, "iface_invoke")
        if pattern is None:
            return self._missing_pattern(control_name, "InvokePattern", control)
        started = time.monotonic()
        before = None
        try:
            pattern.Invoke()
            after = self._state_label()
            expected = "Button invoked" if "Button" in control_type else "Menu invoked"
            return self._result(control_name, "InvokePattern", before, "Invoke()", after, expected, started, control)
        except Exception as exc:
            return self._failed(control_name, "InvokePattern", started, control, exc)

    def set_text(self, value: str) -> ActionResult:
        name = "D3C text input"
        control = self._find(name, "Edit")
        if control is None:
            return self._missing(name, "ValuePattern", self.last_lookup_error)
        pattern = _pattern(control, "iface_value")
        if pattern is None:
            return self._missing_pattern(name, "ValuePattern", control)
        started = time.monotonic()
        before = _value(pattern, "CurrentValue")
        try:
            pattern.SetValue(value)
            after = _value(pattern, "CurrentValue")
            return self._result(name, "ValuePattern", before, f"SetValue({value!r})", after, value, started, control)
        except Exception as exc:
            return self._failed(name, "ValuePattern", started, control, exc, before=before)

    def focus(self, control_name: str, control_type: str) -> ActionResult:
        control = self._find(control_name, control_type)
        if control is None:
            return self._missing(control_name, "Focus", self.last_lookup_error)
        started = time.monotonic()
        before = _focus_state(control)
        try:
            self.adapter.focus(control)
            diagnostic = verify_focus_state(control)
            after = diagnostic["focus_state_after_wait"]
            if diagnostic["result"] == "FOCUS_STATE_UNVERIFIABLE":
                return ActionResult(
                    control_name,
                    "Focus",
                    CapabilityStatus.SUPPORTED_BUT_PATTERN_UNAVAILABLE,
                    before=before,
                    action="SetFocus()",
                    after=after,
                    expected=True,
                    verification="NOT_RUN",
                    error="UIA focus state was not exposed",
                    elapsed_seconds=time.monotonic() - started,
                    control_metadata=_control_metadata(control),
                    diagnostic=diagnostic,
                )
            return self._result(control_name, "Focus", before, "SetFocus()", after, True, started, control, passed=diagnostic["result"] == "VERIFIED", diagnostic=diagnostic)
        except Exception as exc:
            return self._failed(control_name, "Focus", started, control, exc, before=before)

    def toggle(self, control_name: str = "D3C checkbox toggle") -> ActionResult:
        control = self._find(control_name, "CheckBox")
        if control is None:
            return self._missing(control_name, "TogglePattern", self.last_lookup_error)
        pattern = _pattern(control, "iface_toggle")
        if pattern is None:
            return self._missing_pattern(control_name, "TogglePattern", control)
        started = time.monotonic()
        before = _value(pattern, "CurrentToggleState")
        try:
            pattern.Toggle()
            after = _value(pattern, "CurrentToggleState")
            expected = "changed"
            passed = after is not None and after != before
            return self._result(control_name, "TogglePattern", before, "Toggle()", after, expected, started, control, passed=passed)
        except Exception as exc:
            return self._failed(control_name, "TogglePattern", started, control, exc, before=before)

    def select(
        self,
        control_name: str,
        control_type: str,
        item_name: str,
        item_type: str = "ListItem",
    ) -> ActionResult:
        control = self._find(control_name, control_type)
        if control is None:
            return self._missing(control_name, "SelectionItemPattern", self.last_lookup_error)
        if control_type == "ComboBox":
            expand = _pattern(control, "iface_expand_collapse")
            if expand is not None:
                try:
                    expand.Expand()
                except Exception as exc:
                    return self._failed(control_name, "ExpandCollapsePattern", time.monotonic(), control, exc)
        try:
            item = self.adapter.find_control(
                self.window_spec, name=item_name, control_type=item_type
            )
        except UIAError as exc:
            return self._missing(item_name, "SelectionItemPattern", str(exc))
        pattern = _pattern(item, "iface_selection_item")
        if pattern is None:
            return self._missing_pattern(item_name, "SelectionItemPattern", item)
        started = time.monotonic()
        before = _value(pattern, "CurrentIsSelected")
        try:
            pattern.Select()
            after = _value(pattern, "CurrentIsSelected")
            return self._result(item_name, "SelectionItemPattern", before, "Select()", after, True, started, item, passed=after in (True, 1))
        except Exception as exc:
            return self._failed(item_name, "SelectionItemPattern", started, item, exc, before=before)

    def expand_collapse(self, node_name: str, expand: bool) -> ActionResult:
        node = self._find(node_name, "TreeItem")
        if node is None:
            return self._missing(node_name, "ExpandCollapsePattern", self.last_lookup_error)
        pattern = _pattern(node, "iface_expand_collapse")
        if pattern is None:
            return self._missing_pattern(node_name, "ExpandCollapsePattern", node)
        started = time.monotonic()
        before = _value(pattern, "CurrentExpandCollapseState")
        try:
            (pattern.Expand if expand else pattern.Collapse)()
            after = _value(pattern, "CurrentExpandCollapseState")
            expected = 1 if expand else 0
            return self._result(node_name, "ExpandCollapsePattern", before, "Expand()" if expand else "Collapse()", after, expected, started, node)
        except Exception as exc:
            return self._failed(node_name, "ExpandCollapsePattern", started, node, exc, before=before)

    def scroll_to(self, percent: float) -> ActionResult:
        name = "D3C scroll region"
        control = self._find(name, "Pane")
        if control is None:
            return self._missing(name, "ScrollPattern", self.last_lookup_error)
        pattern = _pattern(control, "iface_scroll")
        if pattern is None:
            return self._missing_pattern(name, "ScrollPattern", control)
        started = time.monotonic()
        before = _value(pattern, "CurrentVerticalScrollPercent")
        try:
            pattern.SetScrollPercent(0.0, percent)
            after = _value(pattern, "CurrentVerticalScrollPercent")
            return self._result(name, "ScrollPattern", before, f"SetScrollPercent(0, {percent})", after, percent, started, control, passed=after == percent)
        except Exception as exc:
            return self._failed(name, "ScrollPattern", started, control, exc, before=before)

    def _state_label(self) -> Any:
        state = self._find("Fixture state value", "Text")
        if state is None:
            return None
        return state.window_text()

    def _find(self, name: str, control_type: str):
        try:
            return self.control(name, control_type)
        except UIAError as exc:
            self.last_lookup_error = str(exc)
            return None

    @staticmethod
    def _missing(control: str, primitive: str, error: str | None = None):
        return ActionResult(control, primitive, CapabilityStatus.CONTROL_NOT_EXPOSED, error=error or "Control not exposed")

    @staticmethod
    def _missing_pattern(control: str, primitive: str, wrapper: Any):
        return ActionResult(control, primitive, CapabilityStatus.SUPPORTED_BUT_PATTERN_UNAVAILABLE, control_metadata=_control_metadata(wrapper), error="Pattern unavailable")

    @staticmethod
    def _failed(control, primitive, started, wrapper, exc, *, before=None):
        return ActionResult(control, primitive, CapabilityStatus.ACTION_FAILED, before=before, error=repr(exc), elapsed_seconds=time.monotonic() - started, control_metadata=_control_metadata(wrapper))

    @staticmethod
    def _result(control, primitive, before, action, after, expected, started, wrapper, *, passed=True, diagnostic=None):
        return ActionResult(control, primitive, CapabilityStatus.SUPPORTED if passed else CapabilityStatus.VERIFICATION_FAILED, before, action, after, expected, "PASS" if passed else "FAIL", elapsed_seconds=time.monotonic() - started, control_metadata=_control_metadata(wrapper), diagnostic=diagnostic)


def repeat(operation: str, count: int, action: Callable[[], ActionResult]) -> RepeatabilityResult:
    results = [action() for _ in range(count)]
    passed = sum(item.status == CapabilityStatus.SUPPORTED for item in results)
    return RepeatabilityResult(operation, count, passed, count - passed, results)


def report_to_json(report: ActionReport) -> str:
    def convert(value):
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        if isinstance(value, list):
            return [convert(item) for item in value]
        return value

    return json.dumps(convert(asdict(report)), indent=2, sort_keys=True) + "\n"
