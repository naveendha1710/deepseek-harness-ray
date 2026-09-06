from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable

from desktop_agent.providers.uia import UIAAdapter, UIAError, WindowCandidate
from desktop_agent.fixtures.uia import FIXTURE_TARGETS, FixtureStatus, UIAFixtureManager


class FailureCategory(str, Enum):
    NONE = "none"
    UNAVAILABLE = "unavailable"
    SELECTOR_ISSUE = "selector_issue"
    PATTERN_ACTION_ISSUE = "pattern_action_issue"
    UNSUPPORTED = "unsupported"
    NOT_ATTEMPTED = "not_attempted"


class ApplicationStatus(str, Enum):
    UIA_SUPPORTED = "uia_supported"
    UIA_PARTIAL = "uia_partial"
    UIA_UNSUPPORTED = "uia_unsupported"
    UNAVAILABLE = "unavailable"
    SELECTOR_ISSUE = "selector_issue"
    PATTERN_ACTION_ISSUE = "pattern_action_issue"


@dataclass(frozen=True)
class TargetDefinition:
    app: str
    executable: str
    title_re: str
    launch_command: tuple[str, ...] | None
    expected_control_types: tuple[str, ...]
    safe_test_strategy: str


@dataclass
class PrimitiveResult:
    primitive: str
    attempted: bool
    passed: bool
    failure_category: FailureCategory = FailureCategory.NONE
    error: str | None = None
    control_metadata: dict[str, Any] | None = None


@dataclass
class ApplicationResult:
    app: str
    executable: str
    framework_hints: dict[str, Any] = field(default_factory=dict)
    launchable: bool = False
    fixture_status: str | None = None
    window_found: bool = False
    ui_automation_supported: bool = False
    status: ApplicationStatus = ApplicationStatus.UNAVAILABLE
    controls_found: int = 0
    supported_primitives: list[str] = field(default_factory=list)
    unsupported_primitives: list[str] = field(default_factory=list)
    selector_reliability: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    primitives: list[PrimitiveResult] = field(default_factory=list)


TARGET_DEFINITIONS: tuple[TargetDefinition, ...] = (
    TargetDefinition(
        item.app,
        item.executable,
        item.title_re,
        item.command,
        expected,
        strategy,
    )
    for item, expected, strategy in (
        (FIXTURE_TARGETS[0], ("Document",), "inspect; focus; read text"),
        (FIXTURE_TARGETS[1], ("Tree", "List", "Tab"), "inspect only"),
        (FIXTURE_TARGETS[2], ("List", "Button", "Text"), "inspect only"),
        (FIXTURE_TARGETS[3], ("Button", "Tab"), "inspect; focus only"),
        (FIXTURE_TARGETS[4], ("Edit", "Document"), "inspect only"),
        (FIXTURE_TARGETS[5], ("Tab", "Button"), "inspect only"),
        (FIXTURE_TARGETS[6], ("Tab", "Document"), "inspect only"),
        (FIXTURE_TARGETS[7], ("Button", "Text"), "inspect; focus only"),
    )
)


def _metadata(control: Any) -> dict[str, Any]:
    info = control.element_info
    runtime_id = _safe_attr(info, "runtime_id")
    return {
        "name": _safe_attr(info, "name"),
        "control_type": _safe_attr(info, "control_type"),
        "class_name": _safe_attr(info, "class_name"),
        "framework_id": _safe_attr(info, "framework_id"),
        "pid": _safe_attr(info, "process_id"),
        "handle": _safe_attr(info, "handle"),
        "runtime_id": list(runtime_id) if runtime_id else None,
        "visible": _safe_attr(info, "visible"),
        "enabled": _safe_attr(info, "enabled"),
        "iface_text": _has_pattern(control, "iface_text"),
    }


def _safe_attr(value: Any, name: str) -> Any:
    try:
        return getattr(value, name, None)
    except Exception:
        return None


def _has_pattern(control: Any, pattern_name: str) -> bool:
    try:
        return getattr(control, pattern_name, None) is not None
    except Exception:
        return False


def _primitive(
    name: str,
    attempted: bool,
    passed: bool,
    *,
    category: FailureCategory = FailureCategory.NONE,
    error: str | None = None,
    control: Any | None = None,
) -> PrimitiveResult:
    return PrimitiveResult(
        primitive=name,
        attempted=attempted,
        passed=passed,
        failure_category=category,
        error=error,
        control_metadata=_metadata(control) if control is not None else None,
    )


class UIACompatibilityMatrix:
    """Run conservative UIA compatibility probes against existing windows."""

    def __init__(
        self,
        adapter: UIAAdapter,
        targets: Iterable[TargetDefinition] = TARGET_DEFINITIONS,
        *,
        allow_launch: bool = False,
        fixture_manager: UIAFixtureManager | None = None,
    ):
        self.adapter = adapter
        self.targets = tuple(targets)
        self.allow_launch = allow_launch
        self.fixture_manager = fixture_manager

    def run(self) -> list[ApplicationResult]:
        return [self._run_target(target) for target in self.targets]

    def _run_target(self, target: TargetDefinition) -> ApplicationResult:
        result = ApplicationResult(
            app=target.app,
            executable=target.executable,
            launchable=target.launch_command is not None,
        )
        fixture_target = next(
            (item for item in FIXTURE_TARGETS if item.app == target.app), None
        )
        if self.fixture_manager is not None and fixture_target is not None:
            fixture = self.fixture_manager.acquire(
                fixture_target, allow_launch=self.allow_launch
            )
            candidates = fixture.candidates
            result.framework_hints["fixture"] = {
                "status": fixture.status.value,
                "launched_pid": fixture.launched_pid,
                "elapsed_seconds": round(fixture.elapsed_seconds, 3),
                "selectors_attempted": fixture.selectors_attempted,
                "error": fixture.error,
            }
            result.fixture_status = fixture.status.value
            if fixture.status == FixtureStatus.FIXTURE_LAUNCH_FAILED:
                result.status = ApplicationStatus.UNAVAILABLE
                result.notes.append(fixture.error or fixture.status.value)
                return result
            if fixture.status == FixtureStatus.FIXTURE_UNAVAILABLE:
                result.status = ApplicationStatus.UNAVAILABLE
                result.notes.append(fixture.error or fixture.status.value)
                return result
            if fixture.status == FixtureStatus.SELECTOR_ISSUE:
                result.window_found = bool(candidates)
                result.status = ApplicationStatus.SELECTOR_ISSUE
                result.failure_reasons.append(fixture.error or fixture.status.value)
                return result
            selected_candidate = fixture.selected
        else:
            try:
                candidates = self.adapter.list_window_candidates(target.title_re)
            except UIAError as exc:
                result.status = ApplicationStatus.PATTERN_ACTION_ISSUE
                result.failure_reasons.append(str(exc))
                return result
            selected_candidate = candidates[0] if len(candidates) == 1 else None

        if not candidates:
            result.status = ApplicationStatus.UNAVAILABLE
            result.notes.append("No existing visible UIA window matched the target")
            return result

        result.window_found = True
        result.framework_hints["candidate_count"] = len(candidates)
        result.framework_hints["candidates"] = [self._candidate_json(c) for c in candidates]
        if selected_candidate is None:
            result.status = ApplicationStatus.PATTERN_ACTION_ISSUE
            result.status = ApplicationStatus.SELECTOR_ISSUE
            result.selector_reliability["title_re"] = "ambiguous"
            result.failure_reasons.append(
                f"{len(candidates)} matching windows; handle selection is required"
            )
            result.primitives.append(
                _primitive(
                    "deterministic_window_target",
                    True,
                    False,
                    category=FailureCategory.SELECTOR_ISSUE,
                    error=result.failure_reasons[-1],
                )
            )
            return result

        candidate = selected_candidate
        result.framework_hints.update(
            {
                "pid": candidate.pid,
                "handle": candidate.handle,
                "class_name": candidate.class_name,
                "framework_id": candidate.framework_id,
            }
        )
        result.selector_reliability["handle"] = "passed"
        try:
            window_spec = self.adapter.window_spec_by_handle(candidate.handle)
            window = window_spec.wrapper_object()
            result.ui_automation_supported = True
            result.primitives.extend(
                [
                    _primitive("window_discovery", True, True),
                    _primitive("deterministic_window_target", True, True),
                ]
            )
            controls = window.descendants()
            result.controls_found = len(controls)
            result.primitives.append(_primitive("control_discovery", True, bool(controls)))
            if not controls:
                result.status = ApplicationStatus.UIA_PARTIAL
                result.unsupported_primitives.extend(target.expected_control_types)
                result.notes.append("Window was available but exposed no descendant controls")
                return result
            self._probe_controls(result, target, window_spec, controls)
        except UIAError as exc:
            result.status = ApplicationStatus.PATTERN_ACTION_ISSUE
            result.failure_reasons.append(str(exc))
            result.primitives.append(
                _primitive(
                    "ui_automation_probe",
                    True,
                    False,
                    category=FailureCategory.PATTERN_ACTION_ISSUE,
                    error=str(exc),
                )
            )
            return result
        except Exception as exc:
            result.status = ApplicationStatus.PATTERN_ACTION_ISSUE
            result.failure_reasons.append(repr(exc))
            return result

        attempted_failures = [
            item
            for item in result.primitives
            if item.attempted and not item.passed
        ]
        result.status = (
            ApplicationStatus.UIA_SUPPORTED
            if not attempted_failures
            else ApplicationStatus.UIA_PARTIAL
        )
        return result

    def _probe_controls(self, result, target, window_spec, controls) -> None:
        by_type: dict[str, Any] = {}
        named_control = None
        text_control = None
        for control in controls:
            control_type = _safe_attr(control.element_info, "control_type")
            by_type.setdefault(control_type, control)
            if named_control is None and _safe_attr(control.element_info, "name"):
                named_control = control
            if text_control is None and _has_pattern(control, "iface_text"):
                text_control = control

        for control_type in target.expected_control_types:
            control = by_type.get(control_type)
            if control is None:
                result.unsupported_primitives.append(control_type)
                result.primitives.append(
                    _primitive(
                        f"control_type:{control_type}",
                        True,
                        False,
                        category=FailureCategory.UNSUPPORTED,
                    )
                )
            else:
                result.supported_primitives.append(control_type)
                result.selector_reliability[f"control_type:{control_type}"] = "passed"
                result.primitives.append(
                    _primitive(f"control_type:{control_type}", True, True, control=control)
                )

        if named_control is not None:
            result.supported_primitives.append("semantic_name")
            result.selector_reliability["name"] = "available"
            result.primitives.append(_primitive("semantic_name", True, True, control=named_control))
        else:
            result.unsupported_primitives.append("semantic_name")
            result.primitives.append(
                _primitive("semantic_name", True, False, category=FailureCategory.UNSUPPORTED)
            )

        if text_control is not None:
            try:
                self.adapter.read_text_pattern(text_control)
            except UIAError as exc:
                result.unsupported_primitives.append("read_text")
                result.primitives.append(
                    _primitive(
                        "read_text",
                        True,
                        False,
                        category=FailureCategory.PATTERN_ACTION_ISSUE,
                        error=str(exc),
                        control=text_control,
                    )
                )
            else:
                result.supported_primitives.append("read_text")
                result.primitives.append(_primitive("read_text", True, True, control=text_control))
        else:
            result.unsupported_primitives.append("read_text")
            result.primitives.append(
                _primitive("read_text", True, False, category=FailureCategory.UNSUPPORTED)
            )

        result.primitives.append(
            _primitive(
                "focus",
                False,
                False,
                category=FailureCategory.NOT_ATTEMPTED,
                error="Not attempted by default; focus changes active desktop state",
            )
        )
        for action in ("click", "type", "checkbox", "toggle", "combo_box", "list", "tree", "menu", "tab", "scroll", "selection_state"):
            result.unsupported_primitives.append(action)
            result.primitives.append(
                _primitive(
                    action,
                    False,
                    False,
                    category=FailureCategory.NOT_ATTEMPTED,
                    error="Not attempted by default; compatibility matrix is non-destructive",
                )
            )

        result.notes.append("Action probes are intentionally non-destructive and opt-in work remains for a later phase")

    @staticmethod
    def _candidate_json(candidate: WindowCandidate) -> dict[str, Any]:
        return {
            "title": candidate.title,
            "pid": candidate.pid,
            "handle": candidate.handle,
            "rect": list(candidate.rect) if candidate.rect else None,
            "visible": candidate.visible,
            "enabled": candidate.enabled,
            "class_name": candidate.class_name,
            "framework_id": candidate.framework_id,
        }


def report_to_dict(results: Iterable[ApplicationResult]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "applications": [
            _json_value(asdict(result)) for result in results
        ],
    }


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def report_to_json(results: Iterable[ApplicationResult]) -> str:
    return json.dumps(report_to_dict(results), indent=2, sort_keys=True) + "\n"
