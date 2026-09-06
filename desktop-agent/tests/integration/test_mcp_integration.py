import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from desktop_agent.mcp.server import handle


def test_stdio_protocol_surface():
    response = handle({"jsonrpc": "2.0", "id": "list", "method": "tools/list"})
    names = {item["name"] for item in response["result"]["tools"]}
    assert "desktop_snapshot" in names
    assert "desktop_screenshot" in names


if __name__ == "__main__":
    test_stdio_protocol_surface()
    print("D6B MCP INTEGRATION: PASS")
