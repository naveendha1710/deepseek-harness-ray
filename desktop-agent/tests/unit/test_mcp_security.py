import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from desktop_agent.mcp.tools import CANONICAL_TOOLS


def test_restricted_surface():
    forbidden = {"shell", "python", "send_message", "post_message", "terminate_process", "filesystem", "registry"}
    exposed = set(CANONICAL_TOOLS)
    assert not any(any(word in name.lower() for word in forbidden) for name in exposed)


if __name__ == "__main__":
    test_restricted_surface()
    print("D6B SECURITY SURFACE: PASS")
