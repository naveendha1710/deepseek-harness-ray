import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from desktop_agent.mcp.models import MCPResult, MCPStatus


def test_result_has_required_fields():
    result = MCPResult.start("uia", "desktop_uia_action", {"hwnd": 1}, "focus")
    value = result.finish(MCPStatus.SUCCESS, result={"ok": True}, verification=True, started=0)
    assert value["provider"] == "uia"
    assert value["status"] == "SUCCESS"
    assert "request_id" in value and "duration_ms" in value


if __name__ == "__main__":
    test_result_has_required_fields()
    print("D6B MODEL TESTS: PASS")
