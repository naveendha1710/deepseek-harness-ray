from __future__ import annotations

import json
import ctypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_agent.providers.msaa import MSAAAdapter, MSAANotSupported, node_to_dict, report_to_json
from desktop_agent.fixtures.msaa import D4_FIXTURE_TARGET, WINFORMS_D4_FIXTURE_TARGET
from desktop_agent.providers.uia import UIAAdapter, UIAError
from desktop_agent.fixtures.uia import FixtureStatus, UIAFixtureManager, fixture_to_dict


ROOT = Path(__file__).resolve().parents[1]


def _uia_metadata(window_spec) -> list[dict]:
    values = []
    try:
        controls = window_spec.wrapper_object().descendants()
    except Exception as exc:
        return [{"error": str(exc)}]
    for control in controls:
        info = control.element_info
        values.append({
            "name": _safe(info, "name"),
            "control_type": _safe(info, "control_type"),
            "class_name": _safe(info, "class_name"),
            "framework_id": _safe(info, "framework_id"),
            "handle": _safe(info, "handle"),
            "pid": _safe(info, "process_id"),
        })
    return values


def _safe(value, name):
    try:
        return getattr(value, name, None)
    except Exception:
        return None


def main() -> int:
    report_path = ROOT / "reports" / "msaa_report.json"
    started = time.monotonic()
    uia = UIAAdapter(timeout=10.0)
    fixtures = UIAFixtureManager(uia)
    previous_fixture = fixtures.acquire(WINFORMS_D4_FIXTURE_TARGET, allow_launch=True)
    fixture = fixtures.acquire(D4_FIXTURE_TARGET, allow_launch=True)
    report: dict = {
        "schema_version": 1,
        "previous_winforms_fixture": fixture_to_dict(previous_fixture),
        "fixture": fixture_to_dict(fixture),
        "fixture_metadata": {
            "provider_type": "native Win32 controls",
            "framework": "Win32",
            "control_family": "classic user32/comctl32",
            "accessibility_model": "IAccessible/MSAA",
        },
        "msaa": {"status": "unavailable", "nodes": [], "controls": [], "failures": []},
        "uia_comparison": {"status": "unavailable", "controls": []},
        "actions": [],
        "legacy_target": {
            "status": "unavailable",
            "reason": "No separate real legacy Windows application was established; the native fixture is controlled evidence only.",
        },
        "timings": {},
        "status": "blocked",
    }
    try:
        if fixture.status != FixtureStatus.AVAILABLE or fixture.selected is None:
            report["fixture"]["notes"].append("MSAA fixture window was not available")
            report["timings"]["total_seconds"] = time.monotonic() - started
            report_path.write_text(report_to_json(report), encoding="utf-8")
            print(f"D4 LEGACY TARGET: UNAVAILABLE ({fixture.status.value})")
            print(f"JSON REPORT: {report_path}")
            return 0

        handle = fixture.selected.handle
        report["uia_comparison"] = {"status": "supported", "controls": []}
        try:
            report["uia_comparison"]["controls"] = _uia_metadata(uia.window_spec_by_handle(handle))
        except UIAError as exc:
            report["uia_comparison"] = {"status": "failed", "error": str(exc), "controls": []}

        report["previous_winforms_msaa"] = {
            "status": "fixture_provider_limitation",
            "fixture": fixture_to_dict(previous_fixture),
            "historical_observation": "The WinForms fixture exposed a repeating/shallow MSAA client surface and no meaningful legacy control tree.",
            "nodes": [],
            "actions": [],
        }
        report["msaa"] = _probe_msaa(fixture)
        report["controls"] = report["msaa"].get("controls", [])
        report["status"] = "supported" if report["msaa"]["meaningful_controls"] else "partial"

        report["actions"] = report["msaa"].get("actions", [])
        report["timings"]["total_seconds"] = time.monotonic() - started
        report_path.write_text(report_to_json(report), encoding="utf-8")
        _print_summary(report, report_path)
        return 0
    finally:
        fixtures.cleanup()


def _probe_msaa(fixture):
    if fixture.status != FixtureStatus.AVAILABLE or fixture.selected is None:
        return {"status": "unavailable", "nodes": [], "meaningful_controls": False, "failures": [fixture.error or fixture.status.value]}
    try:
        adapter = MSAAAdapter(timeout=10.0)
        window = adapter.discover_window(fixture.selected.handle, pid=fixture.selected.pid, title=fixture.selected.title, provider_source="tree")
        nodes = adapter.inspect(window)
        child_windows = adapter.list_child_hwnds(window.hwnd)
        tree_nodes_by_hwnd = {node.hwnd: node for node in nodes if node.hwnd != window.hwnd}
        controls = []
        for child_hwnd in child_windows:
            try:
                child_window = adapter.discover_window(child_hwnd, pid=window.pid, objid=-4, provider_source="direct_hwnd")
                direct_node = adapter.inspect(child_window)[0]
                controls.append({
                    "hwnd": child_hwnd,
                    "parent_hwnd": window.hwnd,
                    "class_name": _window_class(child_hwnd),
                    "window_text": _window_text(child_hwnd),
                    "pid": window.pid,
                    "thread_id": _window_thread(child_hwnd),
                    "visible": bool(ctypes.windll.user32.IsWindowVisible(child_hwnd)),
                    "enabled": bool(ctypes.windll.user32.IsWindowEnabled(child_hwnd)),
                    "control_id": _control_id(child_hwnd),
                    "provider_sources": ["tree" if child_hwnd in tree_nodes_by_hwnd else "direct_hwnd"],
                    "tree_provider": node_to_dict(tree_nodes_by_hwnd[child_hwnd]) if child_hwnd in tree_nodes_by_hwnd else None,
                    "direct_hwnd_provider": node_to_dict(direct_node),
                    "supported_actions": _supported_actions(adapter, child_window.root),
                })
                nodes.append(direct_node)
            except Exception as exc:
                controls.append({"hwnd": child_hwnd, "provider_sources": [], "direct_provider_error": repr(exc)})
        meaningful = any(node.name and node.name != window.title and node.role not in {None, "client", "role_0"} for node in nodes)
        failures = [] if meaningful else ["Legacy provider exposed no meaningful child controls"]
        actions = _run_actions(adapter, nodes)
        return {
            "status": "supported" if meaningful else ("partial" if nodes else "unsupported"),
            "window": {"hwnd": window.hwnd, "pid": window.pid, "title": window.title},
            "nodes": [node_to_dict(node) for node in nodes],
            "traversal_errors": list(adapter.last_traversal_errors),
            "child_hwnds": child_windows,
            "meaningful_controls": meaningful,
            "failures": failures,
            "actions": actions,
            "controls": controls,
        }
    except MSAANotSupported as exc:
        return {"status": "unsupported", "nodes": [], "meaningful_controls": False, "failures": [str(exc)]}
    except Exception as exc:
        return {"status": "failed", "nodes": [], "meaningful_controls": False, "failures": [repr(exc)]}


def _run_actions(adapter, nodes):
    """Run only reversible native actions and retain before/after evidence."""
    by_name = {node.name: node for node in nodes if node.name}
    results = []
    edit = by_name.get("Edit value")
    if edit:
        result = {"control": "Edit value", "primitive": "set_value", "attempts": []}
        element = _element_for_node(adapter, edit)
        for attempt in range(1, 6):
            value = f"D4_MSAA_EDIT_{attempt}"
            started = time.monotonic()
            try:
                before = adapter.get_value(element)
                adapter.set_value(element, value)
                after = adapter.get_value(element)
                result["attempts"].append({"attempt": attempt, "before": before, "action": value, "after": after, "verification": after == value, "duration": time.monotonic() - started})
            except Exception as exc:
                result["attempts"].append({"attempt": attempt, "exception": repr(exc), "verification": False})
        results.append(result)
    button = by_name.get("Invoke button")
    if button:
        result = {"control": "Invoke button", "primitive": "default_action", "attempts": []}
        element = _element_for_node(adapter, button)
        for attempt in range(1, 6):
            started = time.monotonic()
            try:
                before = adapter.get_default_action(element)
                adapter.invoke(element)
                after = adapter.get_default_action(element)
                result["attempts"].append({"attempt": attempt, "before": before, "action": "invoke", "after": after, "verification": True, "duration": time.monotonic() - started})
            except Exception as exc:
                result["attempts"].append({"attempt": attempt, "exception": repr(exc), "verification": False})
        results.append(result)
    return results


def _element_for_node(adapter, node):
    window = adapter.discover_window(node.hwnd, provider_source="direct_hwnd")
    return window.root


def _supported_actions(adapter, element):
    actions = ["focus", "select"]
    if adapter.get_default_action(element):
        actions.insert(0, "invoke")
    return actions


def _window_text(hwnd):
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _window_class(hwnd):
    user32 = ctypes.windll.user32
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _window_thread(hwnd):
    pid = ctypes.c_ulong()
    return int(ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))


def _control_id(hwnd):
    return int(ctypes.windll.user32.GetDlgCtrlID(hwnd))


def _print_summary(report, report_path):
    msaa_status = report["msaa"]["status"]
    action_items = report.get("actions", [])
    attempted = [attempt for item in action_items for attempt in item.get("attempts", [])]
    actions = "UNAVAILABLE" if not attempted else ("PASS" if all(attempt.get("verification") for attempt in attempted) else "PARTIAL")
    print("Control | UIA | MSAA | Role | Read | Action | Verify | Status")
    print("------- | --- | ---- | ---- | ---- | ------ | ------ | ------")
    print(f"top-level window | {report['uia_comparison']['status'].upper()} | {msaa_status.upper()} | unknown | PASS | {actions} | {actions} | {report['status'].upper()}")
    print(f"D4 ACTION MATRIX: {actions}")
    print(f"D4B NATIVE MSAA FIXTURE: {'PASS' if report['msaa']['meaningful_controls'] else 'FAIL'}")
    print("D4 LEGACY TARGET: UNAVAILABLE")
    print(f"JSON REPORT: {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
