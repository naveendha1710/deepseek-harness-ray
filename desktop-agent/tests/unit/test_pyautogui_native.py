from __future__ import annotations

import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image
from desktop_agent.providers import pyautogui as native


def test_coordinate_validation():
    original = native._screen
    native._screen = lambda: (100, 100)
    try:
        native.validate_coordinate(99, 99)
        try: native.validate_coordinate(100, 0)
        except native.CoordinateError: pass
        else: raise AssertionError("invalid coordinate accepted")
    finally: native._screen = original


def test_result_status():
    result = native.click(-1, 0)
    assert result.status == native.D6AStatus.COORDINATE_INVALID


def test_report_serialization():
    assert "SUPPORTED" in native.report_to_json({"status": native.D6AStatus.SUPPORTED.value})


def test_screenshot_capture_and_saved_file():
    path = tempfile.gettempdir() + "\\d6a-framework-screenshot.png"
    metadata = native.screenshot(path)
    assert metadata["path"] == path
    with Image.open(path) as image:
        assert image.size == native.screen_size()


def run_suite():
    failures = 0
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        try: test(); print(f"PASS {test.__name__}")
        except Exception as exc: failures += 1; print(f"FAIL {test.__name__}: {exc}")
    print(f"D6A FRAMEWORK: {'PASS' if not failures else 'FAIL'} ({len(tests)-failures}/{len(tests)})")
    return int(bool(failures))


if __name__ == "__main__": raise SystemExit(run_suite())
