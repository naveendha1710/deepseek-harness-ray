from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from desktop_agent.providers.win32 import NativeAmbiguousTarget, NativeTargetNotFound, WindowIdentity, enumerate_windows


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_EXE = ROOT / "fixtures" / "d4-win32-fixture" / "bin" / "Release" / "net8.0-windows" / "D4Win32Fixture.exe"


@dataclass(frozen=True)
class NativeFixtureTarget:
    name: str
    executable: Path
    title: str
    startup_timeout: float = 10.0


@dataclass
class NativeFixture:
    target: NativeFixtureTarget
    process: subprocess.Popen
    window: WindowIdentity


D5_FIXTURE_TARGET = NativeFixtureTarget("D5 Native Win32 Fixture", FIXTURE_EXE, "D4 Native Win32 MSAA Fixture")


class NativeFixtureManager:
    def __init__(self):
        self.owned: list[subprocess.Popen] = []

    def launch(self, target: NativeFixtureTarget = D5_FIXTURE_TARGET) -> NativeFixture:
        if not target.executable.exists():
            raise FileNotFoundError(str(target.executable))
        process = subprocess.Popen([str(target.executable)])
        self.owned.append(process)
        deadline = time.monotonic() + target.startup_timeout
        while time.monotonic() < deadline:
            try:
                windows = [
                    item for item in enumerate_windows()
                    if item.pid == process.pid and item.visible and item.class_name == "D4NativeMsaaFixtureClass"
                ]
                if len(windows) == 1:
                    return NativeFixture(target, process, windows[0])
                if len(windows) > 1:
                    raise NativeAmbiguousTarget(f"Fixture exposed {len(windows)} top-level windows")
            except NativeTargetNotFound:
                pass
            time.sleep(0.1)
        raise TimeoutError(f"Fixture startup timeout: {target.title}")

    def cleanup(self) -> None:
        for process in reversed(self.owned):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill()
        self.owned.clear()
