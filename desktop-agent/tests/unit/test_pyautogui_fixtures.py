import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from desktop_agent.fixtures.pyautogui import FixtureManager


def test_fixture_manager_starts_empty():
    manager = FixtureManager()
    assert manager.owned == []
    manager.cleanup()


if __name__ == "__main__":
    test_fixture_manager_starts_empty(); print("D6A FIXTURE: PASS (1/1)")
