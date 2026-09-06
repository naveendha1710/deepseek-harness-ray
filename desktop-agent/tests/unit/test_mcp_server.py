import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from desktop_agent.mcp.server import handle


def test_initialize_and_list_tools():
    initialized = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    listed = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert initialized["result"]["serverInfo"]["name"] == "desktop-agent"
    assert len(listed["result"]["tools"]) == 12


if __name__ == "__main__":
    test_initialize_and_list_tools()
    print("D6B SERVER TESTS: PASS")
