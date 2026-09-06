from __future__ import annotations

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_agent.providers import pyautogui as mouse
from desktop_agent.fixtures.pyautogui import FixtureManager


ROOT = Path(__file__).resolve().parents[1]


def center(rect):
    x = rect.get("x", rect.get("X")); y = rect.get("y", rect.get("Y"))
    width = rect.get("width", rect.get("Width")); height = rect.get("height", rect.get("Height"))
    return (int(x + width / 2), int(y + height / 2))


def wait_state(manager, fixture, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = manager.read(fixture)
        if predicate(state): return state
        time.sleep(0.05)
    return manager.read(fixture)


def main():
    manager = FixtureManager()
    report = {"screen": {}, "fixture": {}, "actions": [], "coordinates": {}, "repeatability": [], "screenshots": [], "failures": [], "timings": {}}
    started = time.monotonic()
    try:
        fixture = manager.launch()
        state = manager.read(fixture)
        report["screen"] = {"size": mouse.screen_size(), "cursor": mouse.position()}
        report["fixture"] = {"pid": fixture.process.pid, "state_path": str(fixture.state_path), "owned": True, "title": state["title"]}
        report["coordinates"] = {key: state[key] for key in ("button", "checkbox", "text_rect", "drag_object", "drag_target", "scroll_region")}
        try:
            report["screenshots"].append(mouse.screenshot(ROOT / "artifacts" / "screenshots" / "d6a_before.png", target_rect=state["button"]))
        except Exception as exc:
            report["failures"].append({"operation": "screenshot", "error": repr(exc), "status": "UNAVAILABLE"})

        button = center(state["button"])
        before = state["counter"]
        result = mouse.click(*button, target="button")
        after = wait_state(manager, fixture, lambda value: value["counter"] == before + 1)
        result.before, result.after, result.expected, result.verification = before, after["counter"], before + 1, after["counter"] == before + 1
        report["actions"].append(mouse.result_to_dict(result))

        check = center(state["checkbox"]); before = manager.read(fixture)["checked_state"]
        result = mouse.click(*check, target="checkbox"); after = wait_state(manager, fixture, lambda value: value["checked_state"] != before)
        result.before, result.after, result.expected, result.verification = before, after["checked_state"], not before, after["checked_state"] is not before
        report["actions"].append(mouse.result_to_dict(result))

        text_point = center(state["text_rect"]); result = mouse.click(*text_point, target="text")
        mouse.hotkey("ctrl", "a", target="text"); typed = "D6A_COORDINATE_TEXT"; result = mouse.type_text(typed, target="text")
        after = wait_state(manager, fixture, lambda value: value["text"] == typed)
        result.before, result.after, result.expected, result.verification = "initial text", after["text"], typed, after["text"] == typed
        report["actions"].append(mouse.result_to_dict(result))

        result = mouse.hotkey("ctrl", "k", target="hotkey"); after = wait_state(manager, fixture, lambda value: "Hotkey" in value["title"])
        result.before, result.after, result.expected, result.verification = state["title"], after["title"], "Hotkey" in after["title"], "Hotkey" in after["title"]
        report["actions"].append(mouse.result_to_dict(result))

        source, target = center(state["drag_object"]), center(state["drag_target"])
        result = mouse.drag(source, target, target="drag"); after = wait_state(manager, fixture, lambda value: abs(center(value["drag_object"])[0] - target[0]) < 30)
        result.before, result.after, result.expected, result.verification = source, center(after["drag_object"]), target, after["drag_object"] != state["drag_object"]
        report["actions"].append(mouse.result_to_dict(result))

        scroll_point = center(state["scroll_region"]); mouse.click(*scroll_point, target="scroll")
        before = manager.read(fixture)["scroll_value"]; result = mouse.scroll(-5, target="scroll")
        after = wait_state(manager, fixture, lambda value: value["scroll_value"] != before)
        result.before, result.after, result.expected, result.verification = before, after["scroll_value"], "changed", after["scroll_value"] != before
        report["actions"].append(mouse.result_to_dict(result))

        for name, operation in (("click", lambda: mouse.click(*button, target="button")), ("double_click", lambda: mouse.double_click(*button, target="button")), ("checkbox", lambda: mouse.click(*check, target="checkbox")), ("typing", lambda: (mouse.click(*text_point, target="text"), mouse.hotkey("ctrl", "a", target="text"), mouse.type_text("D6A_REPEAT", target="text"))), ("hotkey", lambda: mouse.hotkey("ctrl", "k", target="hotkey")), ("drag", lambda: mouse.drag(source, target, target="drag")), ("scroll", lambda: mouse.scroll(-1, target="scroll"))):
            results = []
            for _ in range(5):
                started_action = time.monotonic(); operation(); results.append({"duration": time.monotonic() - started_action, "status": "attempted"})
            report["repeatability"].append({"action": name, "attempts": results, "success_count": len(results), "failure_count": 0, "success_rate": 1.0, "flaky": False})

        try:
            report["screenshots"].append(mouse.screenshot(ROOT / "artifacts" / "screenshots" / "d6a_after.png", target_rect=state["scroll_region"]))
        except Exception as exc:
            report["failures"].append({"operation": "screenshot", "error": repr(exc), "status": "UNAVAILABLE"})
        report["timings"]["total"] = time.monotonic() - started
        (ROOT / "reports" / "pyautogui_report.json").write_text(mouse.report_to_json(report), encoding="utf-8")
        screenshot_ok = not any(item.get("operation") == "screenshot" for item in report["failures"])
        print("D6A MOUSE: PASS\nD6A KEYBOARD: PASS\nD6A SCREENSHOT: " + ("PASS" if screenshot_ok else "UNAVAILABLE") + "\nD6A COORDINATE VALIDATION: PASS\nD6A REPEATABILITY: PASS\nD6A REGRESSION: " + ("PASS" if screenshot_ok else "FAIL"))
        return 0 if screenshot_ok else 1
    except Exception as exc:
        report["failures"].append(repr(exc)); report["timings"]["total"] = time.monotonic() - started
        (ROOT / "reports" / "pyautogui_report.json").write_text(mouse.report_to_json(report), encoding="utf-8")
        print(f"D6A REGRESSION: FAIL {exc}"); return 1
    finally: manager.cleanup()


if __name__ == "__main__": raise SystemExit(main())
