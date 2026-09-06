from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from desktop_agent.core.uia_actions import (
    ActionReport,
    ActionResult,
    CapabilityStatus,
    RepeatabilityResult,
    report_to_json,
    repeat,
    verify_expected,
    verify_focus_state,
)


def test_action_result_serialization():
    report = ActionReport(
        fixture={"status": "available"},
        controls=[],
        actions=[
            ActionResult(
                "button",
                "InvokePattern",
                CapabilityStatus.SUPPORTED,
                before="Ready",
                action="Invoke()",
                after="Invoked",
                expected="Invoked",
                verification="PASS",
            )
        ],
        repeatability=[],
        failures=[],
        timings={"total": 0.1},
    )
    serialized = report_to_json(report)
    assert '"SUPPORTED"' in serialized
    assert '"Invoke()"' in serialized


def test_capability_classification():
    statuses = {status.value for status in CapabilityStatus}
    assert statuses == {
        "SUPPORTED",
        "SUPPORTED_BUT_PATTERN_UNAVAILABLE",
        "CONTROL_NOT_EXPOSED",
        "ACTION_FAILED",
        "VERIFICATION_FAILED",
        "NOT_APPLICABLE",
    }


def test_expected_state_verification():
    assert verify_expected("after", "after") is True
    assert verify_expected("before", "after") is False


def test_repetition_aggregation():
    count = 0

    def action():
        nonlocal count
        count += 1
        return ActionResult("control", "pattern", CapabilityStatus.SUPPORTED)

    result = repeat("operation", 5, action)
    assert count == 5
    assert result.passed == 5
    assert result.failed == 0


def test_failure_classification_is_preserved():
    result = ActionResult(
        "control",
        "pattern",
        CapabilityStatus.VERIFICATION_FAILED,
        before=False,
        after=True,
        expected=False,
        verification="FAIL",
        error="wrong state",
    )
    assert result.status == CapabilityStatus.VERIFICATION_FAILED
    assert result.error == "wrong state"


def test_failure_injection_categories():
    injected = {
        "invalid selector": CapabilityStatus.CONTROL_NOT_EXPOSED,
        "missing control": CapabilityStatus.CONTROL_NOT_EXPOSED,
        "disabled control": CapabilityStatus.ACTION_FAILED,
        "ambiguous selector": CapabilityStatus.CONTROL_NOT_EXPOSED,
        "wrong expected state": CapabilityStatus.VERIFICATION_FAILED,
        "stale element": CapabilityStatus.ACTION_FAILED,
        "unsupported pattern": CapabilityStatus.SUPPORTED_BUT_PATTERN_UNAVAILABLE,
    }
    results = [
        ActionResult(name, "injected", status)
        for name, status in injected.items()
    ]
    assert {item.status for item in results} == set(injected.values())


class _FocusElement:
    def __init__(self, values):
        self.values = iter(values)
        self.CurrentHasKeyboardFocus = next(self.values)

    def read(self):
        self.CurrentHasKeyboardFocus = next(self.values)
        return self.CurrentHasKeyboardFocus


def test_focus_verified():
    class Control:
        element_info = type("Info", (), {"_element": type("Element", (), {"CurrentHasKeyboardFocus": True})()})()
    assert verify_focus_state(Control(), 0)["result"] == "VERIFIED"


def test_focus_failed():
    class Control:
        element_info = type("Info", (), {"_element": type("Element", (), {"CurrentHasKeyboardFocus": False})()})()
    assert verify_focus_state(Control(), 0)["result"] == "FAILED"


def test_focus_state_unavailable():
    class Control:
        element_info = type("Info", (), {"_element": type("Element", (), {})()})()
    assert verify_focus_state(Control(), 0)["result"] == "FOCUS_STATE_UNVERIFIABLE"


def test_focus_timeout_is_failed_not_passed():
    class Control:
        element_info = type("Info", (), {"_element": type("Element", (), {"CurrentHasKeyboardFocus": False})()})()
    result = verify_focus_state(Control(), 0.001)
    assert result["result"] == "FAILED"


def run_suite() -> int:
    tests = [
        test_action_result_serialization,
        test_capability_classification,
        test_expected_state_verification,
        test_repetition_aggregation,
        test_failure_classification_is_preserved,
        test_failure_injection_categories,
        test_focus_verified,
        test_focus_failed,
        test_focus_state_unavailable,
        test_focus_timeout_is_failed_not_passed,
    ]
    failures = 0
    print("D3C ACTION FRAMEWORK TESTS")
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"D3C ACTION FRAMEWORK: {'PASS' if failures == 0 else 'FAIL'} ({len(tests) - failures}/{len(tests)})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_suite())
