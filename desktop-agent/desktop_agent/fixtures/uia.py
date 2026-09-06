from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum

from desktop_agent.providers.uia import UIAAdapter, UIAError, WindowCandidate


class FixtureStatus(str, Enum):
    AVAILABLE = "available"
    FIXTURE_UNAVAILABLE = "fixture_unavailable"
    FIXTURE_LAUNCH_FAILED = "fixture_launch_failed"
    WINDOW_NOT_FOUND = "window_not_found"
    SELECTOR_ISSUE = "selector_issue"


@dataclass(frozen=True)
class FixtureTarget:
    app: str
    executable: str
    command: tuple[str, ...] | None
    title_re: str
    startup_timeout: float = 5.0
    auto_launch: bool = False
    cleanup_policy: str = "never"
    selection_policy: str = "require_unique"


@dataclass
class FixtureResult:
    app: str
    status: FixtureStatus
    candidates: list[WindowCandidate] = field(default_factory=list)
    selected: WindowCandidate | None = None
    launched_pid: int | None = None
    process_returncode: int | None = None
    command: tuple[str, ...] | None = None
    elapsed_seconds: float = 0.0
    selectors_attempted: list[str] = field(default_factory=list)
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def validate_target(target: FixtureTarget) -> None:
    if not target.app.strip() or not target.executable.strip():
        raise ValueError("Fixture target app and executable are required")
    try:
        re.compile(target.title_re)
    except re.error as exc:
        raise ValueError(f"Invalid title selector: {exc}") from exc
    if target.startup_timeout <= 0:
        raise ValueError("Fixture startup timeout must be positive")
    if target.auto_launch and not target.command:
        raise ValueError("Auto-launch target requires a command")
    if target.selection_policy not in {"require_unique", "lowest_handle"}:
        raise ValueError(f"Unknown fixture selection policy: {target.selection_policy}")


def launch_argv(target: FixtureTarget) -> list[str]:
    validate_target(target)
    if not target.command:
        raise ValueError("Fixture target has no launch command")
    return list(target.command)


FIXTURE_TARGETS: tuple[FixtureTarget, ...] = (
    FixtureTarget("Notepad", "notepad.exe", ("notepad.exe",), r".*Notepad.*", 8.0, True, "terminate_owned", "lowest_handle"),
    FixtureTarget("File Explorer", "explorer.exe", ("explorer.exe",), r".*(File Explorer|Explorer).*", 8.0, False),
    FixtureTarget("Windows Settings", "SystemSettings.exe", ("ms-settings:",), r".*Settings.*", 8.0, False),
    FixtureTarget("Paint", "mspaint.exe", ("mspaint.exe",), r".*Paint.*", 8.0, True, "terminate_owned", "lowest_handle"),
    FixtureTarget("PowerShell", "powershell.exe", ("powershell.exe",), r".*(Windows PowerShell|PowerShell).*", 8.0, True, "terminate_owned", "lowest_handle"),
    FixtureTarget("Windows Terminal", "wt.exe", ("wt.exe",), r".*(Windows Terminal|Terminal).*", 8.0, True, "terminate_owned", "lowest_handle"),
    FixtureTarget("Microsoft Edge", "msedge.exe", ("msedge.exe",), r".*Microsoft Edge.*", 8.0, False),
    FixtureTarget("Calculator", "CalculatorApp.exe", ("calc.exe",), r".*Calculator.*", 8.0, False),
)


class UIAFixtureManager:
    """Acquire visible UIA windows and clean up only explicitly owned launches."""

    def __init__(self, adapter: UIAAdapter):
        self.adapter = adapter
        self._owned: list[subprocess.Popen] = []

    def acquire(self, target: FixtureTarget, *, allow_launch: bool = False) -> FixtureResult:
        validate_target(target)
        started = time.monotonic()
        result = FixtureResult(
            app=target.app,
            status=FixtureStatus.WINDOW_NOT_FOUND,
            command=target.command,
        )
        result.selectors_attempted.append(f"title_re={target.title_re!r}")
        try:
            candidates = self.adapter.list_window_candidates(target.title_re)
        except UIAError as exc:
            result.status = FixtureStatus.FIXTURE_UNAVAILABLE
            result.error = str(exc)
            result.elapsed_seconds = time.monotonic() - started
            return result

        if not candidates and allow_launch and target.auto_launch:
            result = self._launch_and_wait(target, result, started)
            candidates = result.candidates
        else:
            result.candidates = candidates

        if not candidates:
            result.status = (
                FixtureStatus.FIXTURE_UNAVAILABLE
                if not target.auto_launch or not allow_launch
                else FixtureStatus.FIXTURE_LAUNCH_FAILED
            )
            result.error = result.error or "No visible UIA window matched the target"
            result.elapsed_seconds = time.monotonic() - started
            return result

        result.selected, selection_error = self._select(candidates, target.selection_policy)
        if selection_error:
            result.status = FixtureStatus.SELECTOR_ISSUE
            result.error = selection_error
        else:
            result.status = FixtureStatus.AVAILABLE
        result.elapsed_seconds = time.monotonic() - started
        return result

    def cleanup(self) -> None:
        for process in reversed(self._owned):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    pass
        self._owned.clear()

    def _launch_and_wait(self, target, result, started):
        if not target.command:
            result.status = FixtureStatus.FIXTURE_LAUNCH_FAILED
            result.error = "Target has no launch command"
            return result
        try:
            if target.command[0].endswith(":"):
                os.startfile(target.command[0])
                process = None
            else:
                process = subprocess.Popen(launch_argv(target))
        except (OSError, ValueError) as exc:
            result.status = FixtureStatus.FIXTURE_LAUNCH_FAILED
            result.error = repr(exc)
            result.elapsed_seconds = time.monotonic() - started
            return result
        if process is not None:
            self._owned.append(process)
        result.launched_pid = process.pid
        deadline = time.monotonic() + target.startup_timeout
        while time.monotonic() < deadline:
            try:
                candidates = self.adapter.list_window_candidates(target.title_re)
            except UIAError as exc:
                result.error = str(exc)
                candidates = []
            if candidates:
                result.candidates = candidates
                result.notes.append("Visible UIA window appeared after launch")
                return result
            time.sleep(0.2)
        result.status = FixtureStatus.FIXTURE_LAUNCH_FAILED
        result.process_returncode = process.poll() if process is not None else None
        result.error = "Startup timeout expired"
        result.elapsed_seconds = time.monotonic() - started
        result.notes.append("Visible windows discovered after startup timeout: 0")
        return result

    @staticmethod
    def _select(candidates, policy):
        if len(candidates) == 1:
            return candidates[0], None
        if policy == "lowest_handle":
            selected = min(candidates, key=lambda candidate: candidate.handle)
            return selected, None
        details = "; ".join(
            f"title={candidate.title!r}, pid={candidate.pid}, handle={candidate.handle}"
            for candidate in candidates
        )
        return None, f"Ambiguous fixture target ({len(candidates)} candidates): {details}"


def fixture_to_dict(result: FixtureResult) -> dict:
    return {
        "app": result.app,
        "status": result.status.value,
        "candidates": [
            {
                "title": candidate.title,
                "pid": candidate.pid,
                "handle": candidate.handle,
                "rect": list(candidate.rect) if candidate.rect else None,
                "visible": candidate.visible,
                "enabled": candidate.enabled,
            }
            for candidate in result.candidates
        ],
        "selected_handle": result.selected.handle if result.selected else None,
        "launched_pid": result.launched_pid,
        "process_returncode": result.process_returncode,
        "command": list(result.command) if result.command else None,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "selectors_attempted": result.selectors_attempted,
        "error": result.error,
        "notes": result.notes,
    }
