from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from desktop_agent.mcp.tools import tool_definitions


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    names = [f"mcp__desktop__{item['name']}" for item in tool_definitions()]
    config = {
        "transport": "stdio",
        "serverName": "desktop",
        "command": "<absolute path to .desktop-agent-venv\\Scripts\\python.exe>",
        "args": ["-m", "desktop_agent.mcp.server"],
        "cwd": str(ROOT),
        "registered_tool_names": names,
    }
    print(json.dumps(config, indent=2))
    print("D6B DSH INTEGRATION CONFIG: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
