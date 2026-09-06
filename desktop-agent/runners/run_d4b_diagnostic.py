from __future__ import annotations

import ctypes
import re
import subprocess
import sys
import time
from pathlib import Path
from ctypes import wintypes

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_agent.providers.uia import UIAAdapter


ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "fixtures" / "d4-win32-fixture" / "bin" / "Release" / "net8.0-windows" / "D4Win32Fixture.exe"
LOG = Path(__import__("tempfile").gettempdir()) / "d4-native-msaa-fixture.log"

EXPECTED_CONTROLS = (
    ("STATIC", "D4 native MSAA fixture"),
    ("STATIC", "Edit value"),
    ("EDIT", "initial text"),
    ("BUTTON", "Invoke button"),
    ("BUTTON", "Check me"),
    ("BUTTON", "Radio A"),
    ("BUTTON", "Radio B"),
    ("COMBOBOX", ""),
    ("LISTBOX", ""),
    ("SysTreeView32", ""),
    ("SysTabControl32", ""),
    ("STATIC", "Status: ready"),
)


def main() -> int:
    if not EXE.exists():
        print(f"FIXTURE UNAVAILABLE: {EXE}")
        return 0
    LOG.unlink(missing_ok=True)
    process = subprocess.Popen([str(EXE)])
    try:
        deadline = time.monotonic() + 10
        candidates = []
        while time.monotonic() < deadline:
            candidates = [item for item in UIAAdapter().list_window_candidates(r"^D$") if item.pid == process.pid]
            if candidates:
                break
            time.sleep(0.2)
        if not candidates:
            print("WINDOW NOT FOUND")
            return 1
        hwnd = candidates[0].handle
        children = _children(hwnd)
        direct = _direct_children(hwnd)
        print(f"MAIN hwnd={hwnd} pid={process.pid} direct_children={len(direct)} descendants={len(children)}")
        print(f"EXPECTED_CHILDREN={len(EXPECTED_CONTROLS)}")
        print(f"ACTUAL_DIRECT_CHILDREN={len(direct)}")
        print(f"ACTUAL_HWND_DESCENDANTS={len(children)}")
        for child in children:
            print(f"CHILD hwnd={child} parent={ctypes.windll.user32.GetParent(child)} visible={bool(ctypes.windll.user32.IsWindowVisible(child))} enabled={bool(ctypes.windll.user32.IsWindowEnabled(child))}")
        if LOG.exists():
            print("FIXTURE_CREATION_LOG:")
            print(LOG.read_text(encoding="utf-8"))
        actual = [_window_signature(child) for child in direct]
        expected = list(EXPECTED_CONTROLS)
        actual_keys = {_control_key(item) for item in actual}
        expected_keys = {_control_key(item) for item in expected}
        missing = [item for item in expected if _control_key(item) not in actual_keys]
        unexpected = [item for item in actual if _control_key(item) not in expected_keys]
        print(f"MISSING_EXPECTED_CONTROLS={missing}")
        print(f"UNEXPECTED_CONTROLS={unexpected}")
        return 0 if not missing and not unexpected and len(actual) == len(expected) else 1
    finally:
        process.terminate()
        process.wait(timeout=3)


def _children(hwnd: int) -> list[int]:
    result: list[int] = []
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(child, _):
        result.append(int(child))
        return True

    user32.EnumChildWindows(hwnd, callback_type(callback), 0)
    return result


def _direct_children(hwnd: int) -> list[int]:
    result = []
    user32 = ctypes.windll.user32
    child = user32.GetWindow(hwnd, 5)  # GW_CHILD
    while child:
        result.append(int(child))
        child = user32.GetWindow(child, 2)  # GW_HWNDNEXT
    return result


def _window_signature(hwnd: int) -> tuple[str, str]:
    user32 = ctypes.windll.user32
    class_buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_buffer, len(class_buffer))
    text_buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, text_buffer, len(text_buffer))
    return class_buffer.value, text_buffer.value


def _control_key(signature: tuple[str, str]) -> tuple[str, str]:
    return signature[0].casefold(), signature[1]


if __name__ == "__main__":
    raise SystemExit(main())
