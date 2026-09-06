from __future__ import annotations

import re
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from desktop_agent.providers.uia import UIAError, UIAAdapter, WindowCandidate
from desktop_agent.matrix.uia_matrix import (
    ApplicationStatus,
    TargetDefinition,
    UIACompatibilityMatrix,
    report_to_json,
)


def _candidate(title: str, handle: int, pid: int = 100) -> WindowCandidate:
    return WindowCandidate(
        title=title,
        pid=pid,
        handle=handle,
        rect=None,
        visible=True,
        enabled=True,
    )


class _Info:
    def __init__(self, control_type: str, name: str):
        self.control_type = control_type
        self.name = name
        self.class_name = "TestClass"
        self.framework_id = "TestFramework"
        self.process_id = 100
        self.handle = 200
        self.runtime_id = (1, 2, 3)
        self.visible = True
        self.enabled = True


class _Control:
    def __init__(self, control_type: str = "Button", name: str = "Safe"):
        self.element_info = _Info(control_type, name)
        self.iface_text = object()


class _Window:
    def __init__(self, controls):
        self._controls = controls

    def descendants(self):
        return self._controls


class _Spec:
    def __init__(self, window):
        self._window = window

    def wrapper_object(self):
        return self._window


class _FakeAdapter:
    def __init__(self, candidates, controls=None, read_error=None):
        self.candidates = candidates
        self.controls = controls or []
        self.read_error = read_error

    def list_window_candidates(self, title_re):
        return [candidate for candidate in self.candidates if re.search(title_re, candidate.title)]

    def window_spec_by_handle(self, handle):
        return _Spec(_Window(self.controls))

    def read_text_pattern(self, control):
        if self.read_error:
            raise self.read_error
        return "safe text"


def _target(expected=("Button",)):
    return TargetDefinition("Test", "test.exe", r"^Test$", None, expected, "inspect only")


def test_zero_targets():
    assert UIACompatibilityMatrix(_FakeAdapter([]), targets=()).run() == []


def test_optional_unavailable_target():
    result = UIACompatibilityMatrix(_FakeAdapter([]), targets=(_target(),)).run()[0]
    assert result.status == ApplicationStatus.UNAVAILABLE
    assert result.window_found is False


def test_successful_target():
    result = UIACompatibilityMatrix(
        _FakeAdapter([_candidate("Test", 10)], [_Control()]), targets=(_target(),)
    ).run()[0]
    assert result.status == ApplicationStatus.UIA_SUPPORTED
    assert result.controls_found == 1
    assert result.ui_automation_supported is True


def test_partial_support_target():
    result = UIACompatibilityMatrix(
        _FakeAdapter([_candidate("Test", 10)], [_Control("Text")]), targets=(_target(),)
    ).run()[0]
    assert result.status == ApplicationStatus.UIA_PARTIAL
    assert "Button" in result.unsupported_primitives


def test_failed_primitive():
    result = UIACompatibilityMatrix(
        _FakeAdapter(
            [_candidate("Test", 10)],
            [_Control("Button")],
            UIAError("provider failed"),
        ),
        targets=(_target(),),
    ).run()[0]
    assert result.status == ApplicationStatus.UIA_PARTIAL
    read_result = next(item for item in result.primitives if item.primitive == "read_text")
    assert read_result.passed is False
    assert read_result.error == "provider failed"


def test_ambiguous_selector():
    result = UIACompatibilityMatrix(
        _FakeAdapter([_candidate("Test", 10), _candidate("Test", 11)]), targets=(_target(),)
    ).run()[0]
    assert result.status == ApplicationStatus.SELECTOR_ISSUE
    assert result.window_found is True


def test_invalid_selector():
    try:
        UIAAdapter._select_candidate([])
    except UIAError as exc:
        assert "No window matched" in str(exc)
    else:
        raise AssertionError("Invalid empty selector unexpectedly succeeded")


def test_json_serialization():
    result = UIACompatibilityMatrix(_FakeAdapter([]), targets=(_target(),)).run()
    payload = report_to_json(result)
    assert '"applications"' in payload
    assert '"unavailable"' in payload


def test_stable_report_generation():
    first = UIACompatibilityMatrix(_FakeAdapter([]), targets=(_target(),)).run()
    second = UIACompatibilityMatrix(_FakeAdapter([]), targets=(_target(),)).run()
    assert report_to_json(first) == report_to_json(second)


def run_suite() -> int:
    tests = [
        test_zero_targets,
        test_optional_unavailable_target,
        test_successful_target,
        test_partial_support_target,
        test_failed_primitive,
        test_ambiguous_selector,
        test_invalid_selector,
        test_json_serialization,
        test_stable_report_generation,
    ]
    failures = 0
    print("D3B FRAMEWORK TESTS")
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"D3B FRAMEWORK: {'PASS' if failures == 0 else 'FAIL'} ({len(tests) - failures}/{len(tests)})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_suite())
