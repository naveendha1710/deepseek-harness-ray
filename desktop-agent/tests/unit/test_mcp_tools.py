import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from desktop_agent.mcp.tools import CANONICAL_TOOLS, call_tool, tool_definitions


def test_exact_tool_surface():
    expected = {
        "desktop_snapshot", "desktop_find", "desktop_inspect", "desktop_click", "desktop_type", "desktop_read",
        "desktop_invoke", "desktop_select", "desktop_scroll", "desktop_screenshot", "desktop_wait_for", "desktop_assert",
    }
    assert set(CANONICAL_TOOLS) == expected
    assert {item["name"] for item in tool_definitions()} == expected


def test_invalid_hwnd_preserves_target_failure():
    result = call_tool("desktop_window_inspect", {"target": {"hwnd": 0}})
    assert result["status"] == "TARGET_NOT_FOUND"


if __name__ == "__main__":
    test_exact_tool_surface()
    print("D6B TOOL TESTS: PASS")
