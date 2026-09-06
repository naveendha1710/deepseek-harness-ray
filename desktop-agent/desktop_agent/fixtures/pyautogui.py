from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "fixtures" / "d6a-fixture" / "D6AFixture.csproj"
EXE = ROOT / "fixtures" / "d6a-fixture" / "bin" / "Release" / "net8.0-windows" / "D6AFixture.exe"


@dataclass(frozen=True)
class FixtureTarget:
    executable: Path = EXE
    startup_timeout: float = 10.0


@dataclass
class PyAutoGUIFixture:
    process: subprocess.Popen
    state_path: Path
    state: dict


class FixtureManager:
    def __init__(self): self.owned: list[subprocess.Popen] = []

    def launch(self, target=FixtureTarget()) -> PyAutoGUIFixture:
        if not target.executable.exists(): raise FileNotFoundError(str(target.executable))
        state_path = Path(__import__("tempfile").gettempdir()) / f"d6a-fixture-{time.time_ns()}.json"
        process = subprocess.Popen([str(target.executable), str(state_path)])
        self.owned.append(process)
        deadline = time.monotonic() + target.startup_timeout
        while time.monotonic() < deadline:
            if state_path.exists():
                try:
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    if state.get("ready"): return PyAutoGUIFixture(process, state_path, state)
                except json.JSONDecodeError: pass
            time.sleep(0.1)
        raise TimeoutError("D6A fixture startup timeout")

    @staticmethod
    def read(fixture):
        return json.loads(fixture.state_path.read_text(encoding="utf-8"))

    def cleanup(self):
        for process in reversed(self.owned):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill()
        self.owned.clear()
