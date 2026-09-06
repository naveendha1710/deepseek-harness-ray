from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from desktop_agent.fixtures.win32 import D5_FIXTURE_TARGET, NativeFixtureManager


def test_fixture_definition():
    assert D5_FIXTURE_TARGET.title
    assert D5_FIXTURE_TARGET.executable.name.endswith(".exe")


def test_fixture_manager_ownership():
    manager = NativeFixtureManager()
    assert manager.owned == []
    manager.cleanup()
    assert manager.owned == []


def run_suite():
    tests = [test_fixture_definition, test_fixture_manager_ownership]
    failures = 0
    for test in tests:
        try: test(); print(f"PASS {test.__name__}")
        except Exception as exc: failures += 1; print(f"FAIL {test.__name__}: {exc}")
    print(f"D5 FIXTURE: {'PASS' if not failures else 'FAIL'} ({len(tests)-failures}/{len(tests)})")
    return int(bool(failures))


if __name__ == "__main__": raise SystemExit(run_suite())
