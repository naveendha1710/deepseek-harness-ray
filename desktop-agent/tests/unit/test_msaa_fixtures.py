from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from desktop_agent.fixtures.msaa import D4_FIXTURE_TARGET, WINFORMS_D4_FIXTURE_TARGET  # noqa: E402
from desktop_agent.providers.uia import WindowCandidate  # noqa: E402
from desktop_agent.fixtures.uia import (  # noqa: E402
    FixtureStatus,
    FixtureTarget,
    UIAFixtureManager,
    fixture_to_dict,
    launch_argv,
    validate_target,
)


def _candidate(handle):
    return WindowCandidate("Fixture", 42, handle, None, True, True)


def test_d4_target_definition():
    validate_target(D4_FIXTURE_TARGET)
    assert D4_FIXTURE_TARGET.auto_launch is True
    assert D4_FIXTURE_TARGET.cleanup_policy == "terminate_owned"
    assert launch_argv(D4_FIXTURE_TARGET)[0].endswith("D4Win32Fixture.exe")
    assert launch_argv(WINFORMS_D4_FIXTURE_TARGET)[0].endswith("D3CUiaFixture.exe")


def test_unavailable_command_is_reported():
    target = FixtureTarget("Missing", "missing.exe", ("missing.exe",), r"^Missing$", 0.1, True, "terminate_owned", "require_unique")
    validate_target(target)
    assert launch_argv(target) == ["missing.exe"]


def test_owned_cleanup_and_deterministic_selection():
    manager = UIAFixtureManager(type("Adapter", (), {"list_window_candidates": lambda *_: []})())
    selected, error = manager._select([_candidate(20), _candidate(10)], "require_unique")
    assert selected is None and "Ambiguous" in error
    selected, error = manager._select([_candidate(20), _candidate(10)], "lowest_handle")
    assert error is None and selected.handle == 10


def test_fixture_status_serialization():
    class Adapter:
        def list_window_candidates(self, title_re):
            return [_candidate(5)]

    result = UIAFixtureManager(Adapter()).acquire(
        FixtureTarget("Fixture", "x.exe", None, r"^Fixture$"), allow_launch=False
    )
    serialized = fixture_to_dict(result)
    assert result.status == FixtureStatus.AVAILABLE
    assert serialized["selected_handle"] == 5


def run_suite() -> int:
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    failures = 0
    print("D4 MSAA FIXTURE TESTS")
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"D4 FIXTURE: {'PASS' if not failures else 'FAIL'} ({len(tests) - failures}/{len(tests)})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_suite())
