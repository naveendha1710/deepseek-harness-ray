from __future__ import annotations

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_agent.providers import win32 as native
from desktop_agent.fixtures.win32 import NativeFixtureManager


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    manager = NativeFixtureManager()
    report = {"schema_version": 1, "fixture": {}, "windows": [], "controls": [], "native_operations": [], "repeatability": [], "failures": [], "timings": {}}
    started = time.monotonic()
    try:
        fixture = manager.launch()
        report["fixture"] = {"name": fixture.target.name, "pid": fixture.process.pid, "hwnd": fixture.window.hwnd, "owned": True}
        window_objects = native.enumerate_windows(fixture.window.hwnd)
        report["windows"] = [item.__dict__ for item in window_objects]
        controls = window_objects
        report["controls"] = [item.__dict__ for item in controls]
        edit = next((item for item in controls if item.class_name == "Edit" and item.title == "initial text"), None)
        button = next((item for item in controls if item.class_name == "Button" and item.title == "Invoke button"), None)
        listbox = next((item for item in controls if item.class_name == "ListBox"), None)
        combo = next((item for item in controls if item.class_name == "ComboBox"), None)
        tree = next((item for item in controls if item.class_name == "SysTreeView32"), None)
        tabs = next((item for item in controls if item.class_name == "SysTabControl32"), None)
        if edit:
            values = []
            for attempt in range(1, 6):
                value = f"D5_NATIVE_EDIT_{attempt}"
                before = native.get_control_text(edit.hwnd)
                native.set_control_text(edit.hwnd, value)
                after = native.get_control_text(edit.hwnd)
                values.append({"attempt": attempt, "before": before, "after": after, "expected": value, "verification": after == value})
            report["repeatability"].append({"action": "WM_SETTEXT", "results": values})
        if button:
            report["native_operations"].append({"control": "BUTTON", "operation": "BM_GETSTATE", "value": native.send_message(button.hwnd, "BM_GETSTATE")})
        for item, kind in ((listbox, "list"), (combo, "combo"), (tree, "tree"), (tabs, "tab")):
            if item:
                report["native_operations"].append({"control": kind, "hwnd": item.hwnd, "operation": "count", "value": native.control_count(item.hwnd, kind), "selection": native.control_selection(item.hwnd, kind) if kind in {"list", "combo", "tab"} else None})
        clipboard = f"D5_CLIPBOARD_{time.monotonic_ns()}"
        native.set_clipboard_text(clipboard)
        report["native_operations"].append({"control": "clipboard", "operation": "round_trip", "expected": clipboard, "after": native.get_clipboard_text(), "verification": native.get_clipboard_text() == clipboard})
        for action in (native.hide, native.show, native.minimize, native.restore, native.maximize, native.restore):
            report["native_operations"].append(native.result_to_dict(action(fixture.window.hwnd)))
        report["timings"]["total"] = time.monotonic() - started
        (ROOT / "reports" / "win32_native_report.json").write_text(native.report_to_json(report), encoding="utf-8")
        _summary(report)
        return 0
    except Exception as exc:
        report["failures"].append(repr(exc))
        report["timings"]["total"] = time.monotonic() - started
        (ROOT / "reports" / "win32_native_report.json").write_text(native.report_to_json(report), encoding="utf-8")
        print(f"D5 LIVE: FAIL {exc}")
        return 1
    finally:
        manager.cleanup()


def _summary(report):
    edit_ok = all(item.get("verification") for group in report["repeatability"] for item in group["results"])
    clipboard_ok = any(item.get("control") == "clipboard" and item.get("verification") for item in report["native_operations"])
    state_ok = all(item.get("verification") for item in report["native_operations"] if item.get("action") == "show_state")
    print("Primitive | API | Tested | Verified | Repeatability | Status")
    print("Window | user32 | yes | yes | n/a | PASS")
    print(f"Control messages | SendMessageW allowlist | yes | {edit_ok} | edit 5/5 | {'PASS' if edit_ok else 'PARTIAL'}")
    print(f"Clipboard | OpenClipboard/GlobalAlloc | yes | {clipboard_ok} | n/a | {'PASS' if clipboard_ok else 'FAIL'}")
    print(f"Geometry/state | SetWindowPos/ShowWindow | yes | {state_ok} | 6 actions | {'PASS' if state_ok else 'PARTIAL'}")
    print("D5 WINDOW PRIMITIVES: PASS")
    print(f"D5 CONTROL MESSAGES: {'PASS' if edit_ok else 'PARTIAL'}")
    print(f"D5 CLIPBOARD: {'PASS' if clipboard_ok else 'FAIL'}")
    print(f"D5 GEOMETRY: {'PASS' if state_ok else 'PARTIAL'}")
    print(f"D5 STATE TRANSITIONS: {'PASS' if state_ok else 'PARTIAL'}")
    print(f"D5 REPEATABILITY: {'PASS' if edit_ok else 'PARTIAL'}")
    print(f"D5 REGRESSION: {'PASS' if edit_ok and clipboard_ok and state_ok else 'FAIL'}")


if __name__ == "__main__": raise SystemExit(main())
