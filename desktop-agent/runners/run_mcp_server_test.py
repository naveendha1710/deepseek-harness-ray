from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def main() -> int:
    command = [PYTHON, "-m", "desktop_agent.mcp.server"]
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdin and process.stdout
        counter = 0

        def request(method, params=None):
            nonlocal counter
            counter += 1
            value = {"jsonrpc": "2.0", "id": counter, "method": method}
            if params is not None:
                value["params"] = params
            process.stdin.write(json.dumps(value) + "\n")
            process.stdin.flush()
            response = json.loads(process.stdout.readline())
            assert "error" not in response, response
            return response

        request("initialize")
        listed = request("tools/list")
        assert len(listed["result"]["tools"]) == 12
        snapshot_response = request("tools/call", {"name": "desktop_snapshot", "arguments": {}})
        snapshot_text = snapshot_response["result"]["content"][0]["text"]
        snapshot = json.loads(snapshot_text)["result"]
        target = next((item for item in snapshot["elements"] if "Notepad" in (item["metadata"].get("name") or "")), None)
        if target is not None:
            inspected = request("tools/call", {"name": "desktop_inspect", "arguments": {"element_ref": target}})
            inspected_payload = json.loads(inspected["result"]["content"][0]["text"])
            assert inspected_payload["status"] == "SUCCESS"
        request("tools/call", {"name": "desktop_screenshot", "arguments": {}})
        print("D6B MCP SERVER: PASS")
        return 0
    finally:
        if process.stdin:
            process.stdin.close()
        process.terminate()
        process.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
