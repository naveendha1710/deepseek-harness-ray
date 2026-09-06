from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path: sys.path.insert(0, str(PACKAGE_ROOT))

from desktop_agent.providers import win32 as native
from desktop_agent.providers.win32 import NativeAmbiguousTarget, NativeStatus, WindowIdentity, NativeActionResult, result_to_dict, report_to_json


def test_identity_serialization():
    identity = WindowIdentity(1, 2, 3, "x", "BUTTON", "ok", True, True, (0, 0, 10, 10))
    assert json.loads(report_to_json({"window": identity.__dict__}))["window"]["hwnd"] == 1


def test_allowlist_and_result_serialization():
    try: native.send_message(1, "WM_CLOSE")
    except native.NativeUnsupported: pass
    else: raise AssertionError("unsafe message was accepted")
    result = NativeActionResult("x", 1, None, "op", None, None, True, 0.0, None, NativeStatus.SUPPORTED)
    assert result_to_dict(result)["status"] == "SUPPORTED"


def test_selector_rejects_ambiguity(monkeypatch=None):
    original = native.enumerate_windows
    native.enumerate_windows = lambda: [WindowIdentity(1, 2, 3, "x", "A", "same", True, True, None), WindowIdentity(2, 2, 4, "x", "A", "same", True, True, None)]
    try:
        try: native.select_window(title="same")
        except NativeAmbiguousTarget: pass
        else: raise AssertionError("ambiguous target accepted")
    finally: native.enumerate_windows = original


def test_safe_control_message_names():
    assert "WM_GETTEXT" in native.SAFE_MESSAGES
    assert "WM_CLOSE" not in native.SAFE_MESSAGES


def run_suite():
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    failures = 0
    for test in tests:
        try: test(); print(f"PASS {test.__name__}")
        except Exception as exc: failures += 1; print(f"FAIL {test.__name__}: {exc}")
    print(f"D5 FRAMEWORK: {'PASS' if not failures else 'FAIL'} ({len(tests)-failures}/{len(tests)})")
    return int(bool(failures))


if __name__ == "__main__": raise SystemExit(run_suite())
