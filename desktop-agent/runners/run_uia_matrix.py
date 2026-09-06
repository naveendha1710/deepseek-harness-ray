from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_agent.providers.uia import UIAAdapter
from desktop_agent.fixtures.uia import UIAFixtureManager
from desktop_agent.matrix.uia_matrix import UIACompatibilityMatrix, report_to_json


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the UIA compatibility matrix")
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Explicitly launch missing targets using their target definitions",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reports" / "uia_compatibility_report.json",
        help="JSON report path",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    adapter = UIAAdapter(timeout=5.0)
    fixtures = UIAFixtureManager(adapter)
    try:
        results = UIACompatibilityMatrix(
            adapter, allow_launch=args.launch, fixture_manager=fixtures
        ).run()
        args.report.write_text(report_to_json(results), encoding="utf-8")
    finally:
        fixtures.cleanup()

    print("Application | Available | UIA | Click | Type | Read | Controls | Status")
    print("----------- | --------- | --- | ----- | ---- | ---- | -------- | ------")
    for result in results:
        primitive_map = {item.primitive: item for item in result.primitives}
        print(
            f"{result.app} | {result.window_found} | "
            f"{result.ui_automation_supported} | "
            f"{_status(primitive_map, 'click')} | "
            f"{_status(primitive_map, 'type')} | "
            f"{_status(primitive_map, 'read_text')} | "
            f"{result.controls_found} | {result.status.value}"
        )
    statuses = {result.status.value for result in results}
    if "selector_issue" in statuses or "pattern_action_issue" in statuses:
        matrix_status = "FAIL"
    elif "unavailable" in statuses or "uia_partial" in statuses:
        matrix_status = "PARTIAL"
    else:
        matrix_status = "PASS"
    print(f"D3B LIVE MATRIX: {matrix_status}")
    print(f"JSON REPORT: {args.report}")
    return 0


def _status(primitive_map, name: str) -> str:
    primitive = primitive_map.get(name)
    if primitive is None or not primitive.attempted:
        return "not-tested"
    return "pass" if primitive.passed else "fail"


if __name__ == "__main__":
    raise SystemExit(main())
