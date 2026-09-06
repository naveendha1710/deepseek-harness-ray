from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

import pyautogui


class CoordinateError(ValueError):
    pass


class PyAutoGUIActionError(RuntimeError):
    pass


class NativeUnsupported(RuntimeError):
    pass


class D6AStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    COORDINATE_INVALID = "COORDINATE_INVALID"
    ACTION_FAILED = "ACTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    FAILSAFE = "FAILSAFE"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class PyAutoGUIConfig:
    pause: float = 0.1
    failsafe: bool = True
    max_move_distance: float | None = None
    action_timeout: float = 5.0
    minimum_confidence: float = 1.0


@dataclass
class ActionResult:
    action: str
    target: str
    coordinates: object
    timestamp: float
    duration: float
    before: object
    after: object
    expected: object
    verification: bool
    status: D6AStatus
    error: str | None = None


def _screen() -> tuple[int, int]:
    return tuple(int(value) for value in pyautogui.size())


def validate_coordinate(x: int, y: int) -> None:
    width, height = _screen()
    if not (0 <= x < width and 0 <= y < height):
        raise CoordinateError(f"Coordinate ({x}, {y}) outside screen {width}x{height}")


def _call(action, target, coordinates, operation, before=None, expected=None):
    started = time.monotonic()
    timestamp = time.time()
    try:
        result = operation()
        after = result if result is not None else before
        verification = expected is None or after == expected
        return ActionResult(action, target, coordinates, timestamp, time.monotonic() - started, before, after, expected, verification, D6AStatus.SUPPORTED if verification else D6AStatus.VERIFICATION_FAILED)
    except pyautogui.FailSafeException as exc:
        return ActionResult(action, target, coordinates, timestamp, time.monotonic() - started, before, None, expected, False, D6AStatus.FAILSAFE, repr(exc))
    except CoordinateError as exc:
        return ActionResult(action, target, coordinates, timestamp, time.monotonic() - started, before, None, expected, False, D6AStatus.COORDINATE_INVALID, str(exc))
    except Exception as exc:
        return ActionResult(action, target, coordinates, timestamp, time.monotonic() - started, before, None, expected, False, D6AStatus.ACTION_FAILED, repr(exc))


def _mouse_point(x, y):
    validate_coordinate(x, y)
    return x, y


def configure(config: PyAutoGUIConfig) -> None:
    pyautogui.PAUSE = config.pause
    pyautogui.FAILSAFE = config.failsafe


def move(x, y, *, target="screen"):
    return _call("move", target, (x, y), lambda: pyautogui.moveTo(*_mouse_point(x, y)))


def click(x, y, *, target="screen"):
    return _call("click", target, (x, y), lambda: pyautogui.click(*_mouse_point(x, y)))


def double_click(x, y, *, target="screen"):
    return _call("double_click", target, (x, y), lambda: pyautogui.doubleClick(*_mouse_point(x, y)))


def right_click(x, y, *, target="screen"):
    return _call("right_click", target, (x, y), lambda: pyautogui.rightClick(*_mouse_point(x, y)))


def drag(start, end, duration=0.2, *, target="screen"):
    def operation():
        _mouse_point(*start); _mouse_point(*end)
        pyautogui.moveTo(*start); pyautogui.dragTo(*end, duration=duration)
    return _call("drag", target, (start, end), operation)


def scroll(delta, *, target="screen"):
    return _call("scroll", target, delta, lambda: pyautogui.scroll(delta))


def key_press(key, *, target="keyboard"):
    return _call("key_press", target, key, lambda: pyautogui.press(key))


def hotkey(*keys, target="keyboard"):
    return _call("hotkey", target, keys, lambda: pyautogui.hotkey(*keys))


def type_text(text, *, target="keyboard"):
    return _call("type_text", target, text, lambda: pyautogui.write(text))


def screenshot(path: str | Path | None = None, *, target_rect=None):
    image = pyautogui.screenshot()
    output = Path(path) if path else None
    if output: image.save(output)
    return {"timestamp": time.time(), "screen": _screen(), "cursor": position(), "target_rect": target_rect, "path": str(output) if output else None}


def screen_size(): return _screen()


def position():
    point = pyautogui.position()
    return int(point.x), int(point.y)


def result_to_dict(result: ActionResult) -> dict:
    value = asdict(result); value["status"] = result.status.value; return value


def report_to_json(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
