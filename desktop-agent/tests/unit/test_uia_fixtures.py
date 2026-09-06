from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import desktop_agent.fixtures.uia as uia_fixtures
from desktop_agent.providers.uia import WindowCandidate
from desktop_agent.fixtures.uia import (
    FixtureStatus,
    FixtureTarget,
    UIAFixtureManager,
    fixture_to_dict,
    launch_argv,
    validate_target,
)


def _candidate(handle: int) -> WindowCandidate:
    return WindowCandidate("Test", 123, handle, None, True, True)


class _Adapter:
    def __init__(self, sequences):
        self.sequences = iter(sequences)

    def list_window_candidates(self, title_re):
        return next(self.sequences)


def _target(**kwargs) -> FixtureTarget:
    values = {
        "app": "Test",
        "executable": "test.exe",
        "command": ("test.exe", "--safe"),
        "title_re": r"^Test$",
        "startup_timeout": 0.1,
        "auto_launch": True,
        "cleanup_policy": "terminate_owned",
        "selection_policy": "require_unique",
    }
    values.update(kwargs)
    return FixtureTarget(**values)


def test_target_definition_validation():
    validate_target(_target())
    try:
        validate_target(_target(title_re="["))
    except ValueError as exc:
        assert "Invalid title selector" in str(exc)
    else:
        raise AssertionError("Invalid title selector was accepted")


def test_launch_command_generation():
    assert launch_argv(_target()) == ["test.exe", "--safe"]


def test_unavailable_executable():
    adapter = _Adapter([[]])
    manager = UIAFixtureManager(adapter)
    original = uia_fixtures.subprocess.Popen
    uia_fixtures.subprocess.Popen = lambda argv: (_ for _ in ()).throw(FileNotFoundError("missing"))
    try:
        result = manager.acquire(_target(), allow_launch=True)
    finally:
        uia_fixtures.subprocess.Popen = original
    assert result.status == FixtureStatus.FIXTURE_LAUNCH_FAILED
    assert "FileNotFoundError" in result.error


def test_startup_timeout():
    class Process:
        pid = 77

        def poll(self):
            return None

    adapter = _Adapter([[], []])
    original = uia_fixtures.subprocess.Popen
    uia_fixtures.subprocess.Popen = lambda argv: Process()
    try:
        result = UIAFixtureManager(adapter).acquire(
            _target(startup_timeout=0.001), allow_launch=True
        )
    finally:
        uia_fixtures.subprocess.Popen = original
    assert result.status == FixtureStatus.FIXTURE_LAUNCH_FAILED
    assert result.launched_pid == 77
    assert "Startup timeout" in result.error


def test_launched_process_tracking_and_owned_cleanup():
    class Process:
        pid = 88

        def __init__(self):
            self.terminated = False

        def poll(self):
            return None if not self.terminated else 0

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            return 0

    process = Process()
    adapter = _Adapter([[], [_candidate(8)]])
    original = uia_fixtures.subprocess.Popen
    uia_fixtures.subprocess.Popen = lambda argv: process
    manager = UIAFixtureManager(adapter)
    try:
        result = manager.acquire(_target(), allow_launch=True)
    finally:
        uia_fixtures.subprocess.Popen = original
    assert result.status == FixtureStatus.AVAILABLE
    assert manager._owned == [process]
    manager.cleanup()
    assert process.terminated is True
    assert manager._owned == []


def test_cleanup_only_owned_processes():
    class Process:
        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            return 0

    owned = Process()
    unrelated = Process()
    manager = UIAFixtureManager(_Adapter([]))
    manager._owned.append(owned)
    manager.cleanup()
    assert owned.terminated is True
    assert unrelated.terminated is False


def test_deterministic_selection():
    manager = UIAFixtureManager(_Adapter([]))
    selected = manager._select([_candidate(20), _candidate(10)], "lowest_handle")
    assert selected[0].handle == 10
    assert selected[1] is None


def test_ambiguous_selection_rejection():
    manager = UIAFixtureManager(_Adapter([]))
    selected, error = manager._select([_candidate(20), _candidate(10)], "require_unique")
    assert selected is None
    assert "Ambiguous fixture target" in error


def test_fixture_status_serialization():
    result = UIAFixtureManager(_Adapter([[_candidate(3)]])).acquire(_target(auto_launch=False))
    serialized = fixture_to_dict(result)
    assert serialized["status"] == "available"
    assert serialized["selected_handle"] == 3


def run_suite() -> int:
    tests = [
        test_target_definition_validation,
        test_launch_command_generation,
        test_unavailable_executable,
        test_startup_timeout,
        test_launched_process_tracking_and_owned_cleanup,
        test_cleanup_only_owned_processes,
        test_deterministic_selection,
        test_ambiguous_selection_rejection,
        test_fixture_status_serialization,
    ]
    failures = 0
    print("D3B FIXTURE TESTS")
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"D3B FIXTURE: {'PASS' if failures == 0 else 'FAIL'} ({len(tests) - failures}/{len(tests)})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_suite())
