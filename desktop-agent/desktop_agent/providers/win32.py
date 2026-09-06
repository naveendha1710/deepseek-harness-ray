from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import time
from ctypes import wintypes
from dataclasses import asdict, dataclass
from enum import Enum


class NativeError(RuntimeError):
    pass


class NativeAmbiguousTarget(NativeError):
    pass


class NativeTargetNotFound(NativeError):
    pass


class NativeUnsupported(NativeError):
    pass


class NativeStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    ACTION_FAILED = "ACTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NATIVE_UNSUPPORTED = "NATIVE_UNSUPPORTED"


@dataclass
class WindowIdentity:
    hwnd: int
    pid: int
    thread_id: int
    process_name: str | None
    class_name: str
    title: str
    visible: bool
    enabled: bool
    rect: tuple[int, int, int, int] | None


@dataclass
class NativeActionResult:
    action: str
    target: int
    before: object
    native_operation: str
    after: object
    expected: object
    verification: bool
    duration: float
    error: str | None
    status: NativeStatus


SAFE_MESSAGES = frozenset({
    "WM_GETTEXT", "WM_SETTEXT", "EM_GETSEL", "EM_SETSEL", "BM_GETCHECK",
    "BM_SETCHECK", "BM_GETSTATE", "LB_GETCOUNT", "LB_GETTEXT", "LB_GETCURSEL",
    "LB_SETCURSEL", "CB_GETCOUNT", "CB_GETLBTEXT", "CB_GETCURSEL", "CB_SETCURSEL",
    "TVM_GETCOUNT", "TCM_GETITEMCOUNT", "TCM_GETCURSEL", "TCM_SETCURSEL",
})

WM = {"WM_GETTEXT": 0x000D, "WM_SETTEXT": 0x000C, "EM_GETSEL": 0x00B0, "EM_SETSEL": 0x00B1,
      "BM_GETCHECK": 0x00F0, "BM_SETCHECK": 0x00F1, "BM_GETSTATE": 0x00F2,
      "LB_GETCOUNT": 0x018B, "LB_GETTEXT": 0x0189, "LB_GETCURSEL": 0x0188, "LB_SETCURSEL": 0x0186,
      "CB_GETCOUNT": 0x0146, "CB_GETLBTEXT": 0x0148, "CB_GETCURSEL": 0x0147, "CB_SETCURSEL": 0x014E,
      "TVM_GETCOUNT": 0x1105, "TCM_GETITEMCOUNT": 0x1304, "TCM_GETCURSEL": 0x130B, "TCM_SETCURSEL": 0x130C}

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowEnabled.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.EnableWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
user32.SendMessageW.restype = ctypes.c_ssize_t
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GetLastError.restype = wintypes.DWORD
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL


def _text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _class(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _rect(hwnd: int):
    value = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(value)):
        return None
    return (value.left, value.top, value.right, value.bottom)


def window_info(hwnd: int) -> WindowIdentity:
    if not user32.IsWindow(hwnd):
        raise NativeTargetNotFound(f"Invalid HWND: {hwnd}")
    pid = wintypes.DWORD()
    thread_id = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return WindowIdentity(int(hwnd), int(pid.value), int(thread_id), _process_name(int(pid.value)), _class(hwnd), _text(hwnd), bool(user32.IsWindowVisible(hwnd)), bool(user32.IsWindowEnabled(hwnd)), _rect(hwnd))


def _process_name(pid: int) -> str | None:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return os.path.basename(buffer.value)
    finally:
        kernel32.CloseHandle(handle)


def enumerate_windows(parent: int | None = None) -> list[WindowIdentity]:
    values: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    callback = lambda hwnd, _: values.append(int(hwnd)) or True
    if parent is None:
        user32.EnumWindows(callback_type(callback), 0)
    else:
        user32.EnumChildWindows(parent, callback_type(callback), 0)
    return [window_info(hwnd) for hwnd in values]


def select_window(*, hwnd: int | None = None, pid: int | None = None, title: str | None = None, process_name: str | None = None) -> WindowIdentity:
    if hwnd is not None:
        candidate = window_info(hwnd)
        if pid is not None and candidate.pid != pid:
            raise NativeTargetNotFound("HWND does not belong to requested PID")
        if title is not None and candidate.title != title:
            raise NativeTargetNotFound("HWND title does not match exact title")
        return candidate
    candidates = enumerate_windows()
    if pid is not None:
        candidates = [item for item in candidates if item.pid == pid]
    if title is not None:
        candidates = [item for item in candidates if item.title == title]
    if process_name is not None:
        candidates = [item for item in candidates if item.process_name == process_name]
    if not candidates:
        raise NativeTargetNotFound("No native window matched the requested identity")
    if len(candidates) > 1:
        raise NativeAmbiguousTarget("Ambiguous native window target: " + "; ".join(str(item.hwnd) for item in candidates))
    return candidates[0]


def send_message(hwnd: int, message: str, wparam: int = 0, lparam: int = 0) -> int:
    if message not in SAFE_MESSAGES:
        raise NativeUnsupported(f"Message is not allowlisted: {message}")
    return int(user32.SendMessageW(hwnd, WM[message], wparam, lparam))


def get_control_text(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(4096)
    count = user32.SendMessageW(hwnd, WM["WM_GETTEXT"], len(buffer), ctypes.addressof(buffer))
    return buffer.value[: int(count)]


def set_control_text(hwnd: int, text: str) -> None:
    buffer = ctypes.create_unicode_buffer(text)
    result = user32.SendMessageW(hwnd, WM["WM_SETTEXT"], 0, ctypes.addressof(buffer))
    if not result:
        raise NativeError(f"WM_SETTEXT failed for HWND {hwnd}, last_error={ctypes.get_last_error()}")


def control_count(hwnd: int, kind: str) -> int:
    message = {"list": "LB_GETCOUNT", "combo": "CB_GETCOUNT", "tree": "TVM_GETCOUNT", "tab": "TCM_GETITEMCOUNT"}.get(kind)
    if message is None:
        raise NativeUnsupported(f"No count operation for {kind}")
    return send_message(hwnd, message)


def control_selection(hwnd: int, kind: str) -> int:
    message = "LB_GETCURSEL" if kind == "list" else "CB_GETCURSEL" if kind == "combo" else "TCM_GETCURSEL" if kind == "tab" else "BM_GETCHECK" if kind == "button" else None
    if message is None:
        raise NativeUnsupported(f"No selection operation for {kind}")
    return send_message(hwnd, message)


def _show(hwnd, command: int, expected: bool) -> NativeActionResult:
    before = window_info(hwnd).visible
    start = time.monotonic()
    user32.ShowWindow(hwnd, command)
    after = window_info(hwnd).visible
    verified = after == expected
    return NativeActionResult("show_state", hwnd, before, "ShowWindow", after, expected, verified, time.monotonic() - start, None, NativeStatus.SUPPORTED if verified else NativeStatus.VERIFICATION_FAILED)


def show(hwnd): return _show(hwnd, 5, True)
def hide(hwnd): return _show(hwnd, 0, False)
def minimize(hwnd): return _show(hwnd, 6, True)
def maximize(hwnd): return _show(hwnd, 3, True)
def restore(hwnd): return _show(hwnd, 9, True)


def enable(hwnd, value: bool) -> NativeActionResult:
    before = window_info(hwnd).enabled
    user32.EnableWindow(hwnd, value)
    after = window_info(hwnd).enabled
    verified = after == value
    return NativeActionResult("enable", hwnd, before, "EnableWindow", after, value, verified, 0.0, None, NativeStatus.SUPPORTED if verified else NativeStatus.VERIFICATION_FAILED)


def set_position(hwnd: int, x: int, y: int, width: int, height: int) -> NativeActionResult:
    before = window_info(hwnd).rect
    start = time.monotonic()
    user32.SetWindowPos(hwnd, 0, x, y, width, height, 0x0040)
    after = window_info(hwnd).rect
    expected = (x, y, x + width, y + height)
    verified = after == expected
    return NativeActionResult("set_position", hwnd, before, "SetWindowPos", after, expected, verified, time.monotonic() - start, None, NativeStatus.SUPPORTED if verified else NativeStatus.VERIFICATION_FAILED)


def move(hwnd: int, x: int, y: int) -> NativeActionResult:
    rect = window_info(hwnd).rect
    if rect is None: raise NativeError(f"No geometry available for HWND {hwnd}")
    return set_position(hwnd, x, y, rect[2] - rect[0], rect[3] - rect[1])


def resize(hwnd: int, width: int, height: int) -> NativeActionResult:
    rect = window_info(hwnd).rect
    if rect is None: raise NativeError(f"No geometry available for HWND {hwnd}")
    return set_position(hwnd, rect[0], rect[1], width, height)


def center(hwnd: int, work_area: tuple[int, int, int, int]) -> NativeActionResult:
    rect = window_info(hwnd).rect
    if rect is None: raise NativeError(f"No geometry available for HWND {hwnd}")
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    x = work_area[0] + ((work_area[2] - work_area[0]) - width) // 2
    y = work_area[1] + ((work_area[3] - work_area[1]) - height) // 2
    return set_position(hwnd, x, y, width, height)


def set_foreground(hwnd: int) -> NativeActionResult:
    ok = bool(user32.SetForegroundWindow(hwnd))
    return NativeActionResult("set_foreground", hwnd, None, "SetForegroundWindow", ok, True, ok, 0.0, None, NativeStatus.SUPPORTED if ok else NativeStatus.ACTION_FAILED)


def bring_to_front(hwnd: int) -> NativeActionResult:
    ok = bool(user32.BringWindowToTop(hwnd))
    return NativeActionResult("bring_to_front", hwnd, None, "BringWindowToTop", ok, True, ok, 0.0, None, NativeStatus.SUPPORTED if ok else NativeStatus.ACTION_FAILED)


def activate(hwnd: int) -> NativeActionResult:
    return set_foreground(hwnd)


def clear_clipboard() -> None:
    if not user32.OpenClipboard(0): raise NativeError("OpenClipboard failed")
    try:
        if not user32.EmptyClipboard(): raise NativeError("EmptyClipboard failed")
    finally: user32.CloseClipboard()


def set_clipboard_text(text: str) -> None:
    if not user32.OpenClipboard(0): raise NativeError("OpenClipboard failed")
    try:
        clear = user32.EmptyClipboard()
        if not clear: raise NativeError("EmptyClipboard failed")
        data = ctypes.create_unicode_buffer(text)
        handle = kernel32.GlobalAlloc(0x0002, ctypes.sizeof(data))
        if not handle: raise NativeError("GlobalAlloc failed")
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            kernel32.GlobalFree(handle)
            raise NativeError("GlobalLock failed")
        ctypes.memmove(pointer, ctypes.addressof(data), ctypes.sizeof(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(13, handle): raise NativeError("SetClipboardData failed")
    finally: user32.CloseClipboard()


def get_clipboard_text() -> str:
    if not user32.OpenClipboard(0): raise NativeError("OpenClipboard failed")
    try:
        handle = user32.GetClipboardData(13)
        if not handle: return ""
        pointer = kernel32.GlobalLock(handle)
        try: return ctypes.wstring_at(pointer)
        finally: kernel32.GlobalUnlock(handle)
    finally: user32.CloseClipboard()


def result_to_dict(result: NativeActionResult) -> dict:
    value = asdict(result)
    value["status"] = result.status.value
    return value


def report_to_json(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
