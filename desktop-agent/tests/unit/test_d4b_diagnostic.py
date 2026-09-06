from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runners.run_d4b_diagnostic import EXPECTED_CONTROLS, _control_key


def validate_control_set(actual, expected=EXPECTED_CONTROLS):
    actual_keys = {_control_key(item) for item in actual}
    expected_keys = {_control_key(item) for item in expected}
    missing = [item for item in expected if _control_key(item) not in actual_keys]
    unexpected = [item for item in actual if _control_key(item) not in expected_keys]
    return missing, unexpected


def test_expected_count_comes_from_authoritative_definition():
    assert len(EXPECTED_CONTROLS) == 12


def test_missing_expected_control_fails():
    missing, unexpected = validate_control_set(list(EXPECTED_CONTROLS[:-1]))
    assert missing == [EXPECTED_CONTROLS[-1]]
    assert unexpected == []


def test_unexpected_control_fails_deterministically():
    actual = list(EXPECTED_CONTROLS) + [("STATIC", "unexpected")]
    missing, unexpected = validate_control_set(actual)
    assert missing == []
    assert unexpected == [("STATIC", "unexpected")]


def test_class_matching_is_case_insensitive_but_title_is_exact():
    actual = [(class_name.title(), title) for class_name, title in EXPECTED_CONTROLS]
    missing, unexpected = validate_control_set(actual)
    assert missing == []
    assert unexpected == []
    missing, unexpected = validate_control_set(actual[:-1] + [("Static", "wrong title")])
    assert missing == [EXPECTED_CONTROLS[-1]]
    assert unexpected == [("Static", "wrong title")]


def run_suite() -> int:
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"D4B DIAGNOSTIC TESTS: {'PASS' if not failures else 'FAIL'} ({len(tests) - failures}/{len(tests)})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_suite())
