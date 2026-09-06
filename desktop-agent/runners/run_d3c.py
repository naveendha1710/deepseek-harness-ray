from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_agent.providers.uia import UIAAdapter, UIAError
from desktop_agent.core.uia_actions import (
    ActionReport,
    ActionResult,
    CapabilityStatus,
    D3CActionProbe,
    RepeatabilityResult,
    report_to_json,
    repeat,
)
from desktop_agent.fixtures.uia import FixtureTarget, FixtureStatus, UIAFixtureManager, fixture_to_dict


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_EXE = ROOT / "fixtures" / "d3c-fixture" / "bin" / "Release" / "net8.0-windows" / "D3CUiaFixture.exe"
FIXTURE_TARGET = FixtureTarget(
    "D3C UIA Fixture",
    "D3CUiaFixture.exe",
    (str(FIXTURE_EXE),),
    r"^D3C UIA Fixture(?: Window)?$",
    startup_timeout=10.0,
    auto_launch=True,
    cleanup_policy="terminate_owned",
    selection_policy="require_unique",
)


def _repeat_action(operation: str, count: int, action) -> RepeatabilityResult:
    return repeat(operation, count, action)


def _round_trip_checkbox(probe: D3CActionProbe) -> ActionResult:
    first = probe.toggle()
    second = probe.toggle()
    return second if first.status == CapabilityStatus.SUPPORTED else first


def main() -> int:
    report_path = ROOT / "reports" / "uia_action_report.json"
    adapter = UIAAdapter(timeout=10.0)
    fixtures = UIAFixtureManager(adapter)
    started = time.monotonic()
    fixture = fixtures.acquire(FIXTURE_TARGET, allow_launch=True)
    actions: list[ActionResult] = []
    repeats: list[RepeatabilityResult] = []
    controls: list[dict] = []
    failures: list[str] = []

    try:
        if fixture.status != FixtureStatus.AVAILABLE or fixture.selected is None:
            failures.append(fixture.error or fixture.status.value)
            report = ActionReport(
                fixture=fixture_to_dict(fixture),
                controls=[],
                actions=[],
                repeatability=[],
                failures=failures,
                timings={"total": time.monotonic() - started},
            )
            report_path.write_text(report_to_json(report), encoding="utf-8")
            print(f"D3C ACTION MATRIX: BLOCKED ({fixture.status.value})")
            return 0

        window_spec = adapter.window_spec_by_handle(fixture.selected.handle)
        window = window_spec.wrapper_object()
        controls = [_control_metadata(control) for control in window.descendants()]
        probe = D3CActionProbe(adapter, window_spec)

        text_results = repeat(
            "text_write_read",
            5,
            lambda: probe.set_text(f"D3C_TEXT_{time.monotonic_ns()}"),
        )
        repeats.append(text_results)
        actions.extend(text_results.results)

        focus_result = probe.focus("D3C text input", "Edit")
        actions.append(focus_result)

        button_results = repeat("button_invoke", 5, lambda: probe.invoke("D3C invoke button"))
        repeats.append(button_results)
        actions.extend(button_results.results)

        checkbox_results = repeat(
            "checkbox_toggle_round_trip", 5, lambda: _round_trip_checkbox(probe)
        )
        repeats.append(checkbox_results)
        actions.extend(checkbox_results.results)

        for operation, call in (
            ("combo_selection", lambda: probe.select("D3C combo selection", "ComboBox", "Blue")),
            ("list_selection", lambda: probe.select("D3C list selection", "List", "Beta")),
            ("tree_expand", lambda: probe.expand_collapse("Root", True)),
            ("tree_collapse", lambda: probe.expand_collapse("Root", False)),
            ("tab_selection", lambda: probe.select("D3C tab selection", "Tab", "Second", "TabItem")),
            ("menu_invoke", lambda: probe.invoke("D3C safe menu action", "MenuItem")),
            ("scroll", lambda: probe.scroll_to(100.0)),
        ):
            results = repeat(operation, 5, call)
            repeats.append(results)
            actions.extend(results.results)

        failures.extend(
            f"{item.control}/{item.primitive}: {item.error or item.verification}"
            for item in actions
            if item.status in {
                CapabilityStatus.ACTION_FAILED,
                CapabilityStatus.VERIFICATION_FAILED,
            }
        )
        report = ActionReport(
            fixture=fixture_to_dict(fixture),
            controls=controls,
            actions=actions,
            repeatability=repeats,
            failures=failures,
            timings={"total": time.monotonic() - started},
        )
        report_path.write_text(report_to_json(report), encoding="utf-8")
        _print_summary(actions, repeats, report_path)
        return 0
    finally:
        fixtures.cleanup()


def _control_metadata(control) -> dict:
    info = control.element_info
    return {
        "name": _safe(info, "name"),
        "control_type": _safe(info, "control_type"),
        "auto_id": _safe(info, "automation_id"),
        "class_name": _safe(info, "class_name"),
        "framework_id": _safe(info, "framework_id"),
        "pid": _safe(info, "process_id"),
        "handle": _safe(info, "handle"),
        "runtime_id": list(_safe(info, "runtime_id") or []),
        "visible": _safe(info, "visible"),
        "enabled": _safe(info, "enabled"),
    }


def _safe(value, name):
    try:
        return getattr(value, name, None)
    except Exception:
        return None


def _print_summary(actions, repeats, report_path):
    grouped = {}
    for item in actions:
        grouped.setdefault(item.control, []).append(item)
    print("Control | Discover | Pattern | Action | Verify | Repeatability | Status")
    print("------- | --------- | ------- | ------ | ------ | ------------- | ------")
    for control, items in grouped.items():
        successful = sum(item.status == CapabilityStatus.SUPPORTED for item in items)
        failures = len(items) - successful
        status = "PASS" if failures == 0 else "PARTIAL"
        print(f"{control} | PASS | UIA | {successful}/{len(items)} | {successful}/{len(items)} | {successful}/{len(items)} | {status}")
    action_status = "PASS" if all(item.status == CapabilityStatus.SUPPORTED for item in actions) else "PARTIAL"
    repeat_status = "PASS" if all(item.failed == 0 for item in repeats) else "PARTIAL"
    print(f"D3C ACTION MATRIX: {action_status}")
    print(f"D3C REPEATABILITY: {repeat_status}")
    print(f"JSON REPORT: {report_path}")


if __name__ == "__main__":
    raise SystemExit(main())
