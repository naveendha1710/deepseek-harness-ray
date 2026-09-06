from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from desktop_agent.providers.msaa import (  # noqa: E402
    AccessibilityNode,
    ActionStatus,
    FailureCategory,
    MSAAActionResult,
    MSAAAdapter,
    MSAAAmbiguousTarget,
    MSAAElement,
    MSAAElementNotFound,
    action_to_dict,
    node_to_dict,
    normalize_role,
    normalize_state,
    report_to_json,
)


class FakeAdapter(MSAAAdapter):
    def __init__(self, elements, children):
        self.elements = elements
        self.children = children
        self.last_traversal_errors = []

    def walk(self, root, *, max_depth=32, max_nodes=5000):
        return super().walk(root, max_depth=max_depth, max_nodes=max_nodes)

    def get_children(self, element):
        return list(self.children.get(element.id, []))

    def get_name(self, element):
        return self.elements[element.id][0]

    def get_role(self, element):
        return self.elements[element.id][1]

    def get_state(self, element):
        return 0

    def get_value(self, element):
        return None

    def get_description(self, element):
        return None

    def get_default_action(self, element):
        return None


def _tree():
    root = MSAAElement(None, 1, id="root")
    button = MSAAElement(None, 1, parent_id="root", id="button")
    edit = MSAAElement(None, 1, parent_id="root", id="edit")
    elements = {"root": ("Main", "window"), "button": ("Apply", "push button"), "edit": ("Name", "editable text")}
    return root, button, edit, elements, {"root": [button, edit], "button": [], "edit": []}


def test_role_and_state_normalization():
    assert normalize_role(23) == "push button"
    assert normalize_role(999) == "role_999"
    assert normalize_state(3) == 3


def test_serialization():
    node = AccessibilityNode("x", None, "Name", "window", 0, None, None, 1, 0)
    result = MSAAActionResult("focus", "x", ActionStatus.VERIFIED, elapsed_seconds=0.1)
    assert json.loads(report_to_json({"node": node_to_dict(node), "action": action_to_dict(result)}))["node"]["id"] == "x"


def test_deterministic_target_and_ambiguity():
    root, button, edit, elements, children = _tree()
    adapter = FakeAdapter(elements, children)
    window = type("Window", (), {"root": root})()
    assert adapter.find_control(window, name="Apply").id == "button"
    try:
        adapter.find_control(window, role="editable text", name="missing")
    except MSAAElementNotFound:
        pass
    else:
        raise AssertionError("missing MSAA element was accepted")
    children["root"].append(MSAAElement(None, 1, parent_id="root", id="button2"))
    elements["button2"] = ("Apply", "push button")
    try:
        adapter.find_control(window, name="Apply")
    except MSAAAmbiguousTarget:
        pass
    else:
        raise AssertionError("ambiguous MSAA target was accepted")


def test_cycle_depth_and_node_limits_are_reported():
    root, button, _, elements, children = _tree()
    children["button"] = [root]
    adapter = FakeAdapter(elements, children)
    assert len(adapter.walk(root, max_depth=1)) == 3
    assert adapter.last_traversal_errors
    assert len(adapter.walk(root, max_nodes=1)) == 1
    assert adapter.last_traversal_errors


def run_suite() -> int:
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    failures = 0
    print("D4 MSAA UNIT TESTS")
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"PASS {test.__name__}")
    print(f"D4 FRAMEWORK: {'PASS' if not failures else 'FAIL'} ({len(tests) - failures}/{len(tests)})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run_suite())
