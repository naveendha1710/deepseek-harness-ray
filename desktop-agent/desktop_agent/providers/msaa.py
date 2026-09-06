from __future__ import annotations

import ctypes
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from comtypes import COMMETHOD, GUID, HRESULT, POINTER, cast
from comtypes.automation import BSTR, IDispatch, VARIANT
from ctypes import wintypes


class MSAAError(RuntimeError):
    """Base error for Microsoft Active Accessibility operations."""


class MSAANotSupported(MSAAError):
    pass


class MSAAElementNotFound(MSAAError):
    pass


class MSAAAmbiguousTarget(MSAAError):
    pass


class MSAAActionError(MSAAError):
    pass


class MSAAVerificationError(MSAAError):
    pass


class FailureCategory(str, Enum):
    WINDOW_NOT_FOUND = "window_not_found"
    ELEMENT_NOT_FOUND = "element_not_found"
    AMBIGUOUS_TARGET = "ambiguous_target"
    MSAA_UNAVAILABLE = "msaa_unavailable"
    ROLE_UNAVAILABLE = "role_unavailable"
    PROPERTY_UNAVAILABLE = "property_unavailable"
    ACTION_UNAVAILABLE = "action_unavailable"
    ACTION_FAILED = "action_failed"
    VERIFICATION_FAILED = "verification_failed"
    TRAVERSAL_FAILED = "traversal_failed"
    TIMEOUT = "timeout"


class ActionStatus(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class MSAAActionResult:
    action: str
    element_id: str
    status: ActionStatus
    before: Any = None
    after: Any = None
    expected: Any = None
    error: str | None = None
    failure_category: FailureCategory | None = None
    elapsed_seconds: float = 0.0


def normalize_role(value: Any) -> str | None:
    """Convert an MSAA role VARIANT or integer to a stable role name."""
    raw = _variant_value(value) if isinstance(value, VARIANT) else value
    try:
        raw = int(raw)
    except (TypeError, ValueError):
        return str(raw) if raw is not None else None
    return ROLE_NAMES.get(raw, f"role_{raw}")


def normalize_state(value: Any) -> int | str | None:
    """Retain MSAA state flags while making VARIANT values JSON-friendly."""
    raw = _variant_value(value) if isinstance(value, VARIANT) else value
    try:
        return int(raw)
    except (TypeError, ValueError):
        return str(raw) if raw is not None else None


def node_to_dict(node: AccessibilityNode) -> dict[str, Any]:
    return {
        "id": node.id, "parent_id": node.parent_id, "name": node.name,
        "role": node.role, "state": node.state, "value": node.value,
        "description": node.description, "hwnd": node.hwnd,
        "child_id": node.child_id, "children": node.children,
        "default_action": node.default_action, "child_count": node.child_count,
        "traversal_error": node.traversal_error,
    }


def action_to_dict(result: MSAAActionResult) -> dict[str, Any]:
    value = result.__dict__.copy()
    value["status"] = result.status.value
    value["failure_category"] = result.failure_category.value if result.failure_category else None
    return value


def report_to_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


class IAccessible(IDispatch):
    _iid_ = GUID("{618736e0-3c3d-11cf-810c-00aa00389b71}")
    _methods_ = [
        COMMETHOD([], HRESULT, "get_accParent", (['out'], POINTER(POINTER(IDispatch)), "parent")),
        COMMETHOD([], HRESULT, "get_accChildCount", (['out'], POINTER(ctypes.c_long), "count")),
        COMMETHOD([], HRESULT, "get_accChild", (['in'], VARIANT, "child"), (['out'], POINTER(POINTER(IDispatch)), "child_object")),
        COMMETHOD([], HRESULT, "get_accName", (['in'], VARIANT, "child"), (['out'], POINTER(BSTR), "value")),
        COMMETHOD([], HRESULT, "get_accValue", (['in'], VARIANT, "child"), (['out'], POINTER(BSTR), "value")),
        COMMETHOD([], HRESULT, "get_accDescription", (['in'], VARIANT, "child"), (['out'], POINTER(BSTR), "value")),
        COMMETHOD([], HRESULT, "get_accRole", (['in'], VARIANT, "child"), (['out'], POINTER(VARIANT), "value")),
        COMMETHOD([], HRESULT, "get_accState", (['in'], VARIANT, "child"), (['out'], POINTER(VARIANT), "value")),
        COMMETHOD([], HRESULT, "get_accHelp", (['in'], VARIANT, "child"), (['out'], POINTER(BSTR), "value")),
        COMMETHOD([], HRESULT, "get_accHelpTopic", (['out'], POINTER(BSTR), "file"), (['in'], VARIANT, "child"), (['out'], POINTER(ctypes.c_long), "id")),
        COMMETHOD([], HRESULT, "get_accKeyboardShortcut", (['in'], VARIANT, "child"), (['out'], POINTER(BSTR), "value")),
        COMMETHOD([], HRESULT, "get_accFocus", (['out'], POINTER(VARIANT), "value")),
        COMMETHOD([], HRESULT, "get_accSelection", (['out'], POINTER(VARIANT), "value")),
        COMMETHOD([], HRESULT, "get_accDefaultAction", (['in'], VARIANT, "child"), (['out'], POINTER(BSTR), "value")),
        COMMETHOD([], HRESULT, "accSelect", (['in'], ctypes.c_long, "flags"), (['in'], VARIANT, "child")),
        COMMETHOD([], HRESULT, "accLocation", (['out'], POINTER(ctypes.c_long), "left"), (['out'], POINTER(ctypes.c_long), "top"), (['out'], POINTER(ctypes.c_long), "width"), (['out'], POINTER(ctypes.c_long), "height"), (['in'], VARIANT, "child")),
        COMMETHOD([], HRESULT, "accNavigate", (['in'], ctypes.c_long, "direction"), (['in'], VARIANT, "start"), (['out'], POINTER(VARIANT), "end")),
        COMMETHOD([], HRESULT, "accHitTest", (['in'], ctypes.c_long, "x"), (['in'], ctypes.c_long, "y"), (['out'], POINTER(VARIANT), "child")),
        COMMETHOD([], HRESULT, "accDoDefaultAction", (['in'], VARIANT, "child")),
        COMMETHOD([], HRESULT, "put_accName", (['in'], VARIANT, "child"), (['in'], BSTR, "value")),
        COMMETHOD([], HRESULT, "put_accValue", (['in'], VARIANT, "child"), (['in'], BSTR, "value")),
    ]


ROLE_NAMES = {
    9: "window", 10: "client", 6: "check button", 7: "radio button",
    8: "combo box", 12: "dialog", 15: "editable text", 16: "list",
    18: "list item", 19: "menu", 20: "menu item", 21: "page tab",
    23: "push button", 24: "scrollbar", 25: "static text", 26: "tree",
    37: "tree item",
    33: "list",
    35: "outline",
    41: "static text",
    42: "editable text",
    43: "push button",
    44: "check button",
    45: "radio button",
    46: "combo box",
    60: "page tab list",
}


def _child(value: int = 0) -> VARIANT:
    return VARIANT(value)


def _variant_value(value: VARIANT) -> Any:
    try:
        return value.value
    except Exception:
        return None


@dataclass
class AccessibilityNode:
    id: str
    parent_id: str | None
    name: str | None
    role: str | None
    state: Any
    value: str | None
    description: str | None
    hwnd: int | None
    child_id: int
    children: list[str] = field(default_factory=list)
    default_action: str | None = None
    child_count: int | None = None
    traversal_error: str | None = None


@dataclass
class MSAAElement:
    interface: IAccessible
    hwnd: int
    child_id: int = 0
    parent_id: str | None = None
    id: str = ""
    provider_source: str = "tree"


@dataclass
class MSAAWindow:
    hwnd: int
    pid: int
    title: str
    root: MSAAElement


class MSAAAdapter:
    """Independent IAccessible adapter using oleacc.dll and VARIANT child IDs."""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout
        self._oleacc = ctypes.OleDLL("oleacc.dll")
        self._oleacc.AccessibleObjectFromWindow.argtypes = [
            wintypes.HWND, wintypes.DWORD, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)
        ]
        self._oleacc.AccessibleObjectFromWindow.restype = ctypes.HRESULT
        self.last_traversal_errors: list[str] = []

    def discover_window(self, hwnd: int, *, pid: int | None = None, title: str | None = None, objid: int = -4, provider_source: str = "tree") -> MSAAWindow:
        interface = self._from_hwnd(hwnd, objid=objid)
        return MSAAWindow(hwnd, pid if pid is not None else self._pid(hwnd), title or self._title(hwnd), MSAAElement(interface, hwnd, id=f"{hwnd}:0", provider_source=provider_source))

    def list_windows(self, title_re: str = ".*") -> list[tuple[int, int, str]]:
        matches: list[tuple[int, int, str]] = []
        pattern = re.compile(title_re)
        user32 = ctypes.windll.user32
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                title = self._title(hwnd)
                if pattern.match(title):
                    matches.append((int(hwnd), self._pid(hwnd), title))
            return True

        user32.EnumWindows(enum_proc(callback), 0)
        return matches

    def find_control(self, window: MSAAWindow, *, name: str | None = None, role: str | None = None, path: tuple[int, ...] | None = None) -> MSAAElement:
        if path is not None:
            current = window.root
            for index in path:
                children = self.get_children(current)
                if index >= len(children):
                    raise MSAAElementNotFound(f"Child index {index} missing at {current.id}")
                current = children[index]
            return current
        matches = [node for node in self.walk(window.root) if (name is None or self.get_name(node) == name) and (role is None or self.get_role(node) == role)]
        if not matches:
            raise MSAAElementNotFound(f"No MSAA element matched name={name!r} role={role!r}")
        if len(matches) > 1:
            raise MSAAAmbiguousTarget(f"{len(matches)} MSAA elements matched name={name!r} role={role!r}")
        return matches[0]

    def get_name(self, element: MSAAElement) -> str | None:
        return self._bstr(element, "get_accName")

    def get_value(self, element: MSAAElement) -> str | None:
        return self._bstr(element, "get_accValue")

    def get_description(self, element: MSAAElement) -> str | None:
        return self._bstr(element, "get_accDescription")

    def get_default_action(self, element: MSAAElement) -> str | None:
        return self._bstr(element, "get_accDefaultAction")

    def get_role(self, element: MSAAElement) -> str | None:
        try:
            value = element.interface.get_accRole(_child(element.child_id))
            return normalize_role(value)
        except Exception:
            return None

    def get_state(self, element: MSAAElement) -> Any:
        try:
            value = element.interface.get_accState(_child(element.child_id))
            return normalize_state(value)
        except Exception:
            return None

    def get_children(self, element: MSAAElement) -> list[MSAAElement]:
        try:
            count = element.interface.get_accChildCount()
        except Exception as exc:
            raise MSAAError(f"Child count failed for {element.id}: {exc}") from exc
        children: list[MSAAElement] = []
        for child_id in range(1, count + 1):
            try:
                dispatch = element.interface.get_accChild(_child(child_id))
            except Exception:
                continue
            if dispatch:
                interface = cast(dispatch, POINTER(IAccessible))
                child = MSAAElement(interface, element.hwnd, 0, element.id, f"{element.id}/{child_id}:0")
            else:
                child = MSAAElement(element.interface, element.hwnd, child_id, element.id, f"{element.id}/{child_id}")
            children.append(child)
        return children

    def list_child_hwnds(self, hwnd: int) -> list[int]:
        """Enumerate owned native child HWNDs for providers without a child tree."""
        result: list[int] = []
        user32 = ctypes.windll.user32
        enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def callback(child, _):
            result.append(int(child))
            return True

        user32.EnumChildWindows(hwnd, enum_proc(callback), 0)
        return result

    def walk(self, root: MSAAElement, *, max_depth: int = 32, max_nodes: int = 5000) -> list[MSAAElement]:
        self.last_traversal_errors = []
        result: list[MSAAElement] = []
        seen: set[tuple[int, int, str]] = set()
        stack: list[tuple[MSAAElement, int]] = [(root, 0)]
        while stack and len(result) < max_nodes:
            element, depth = stack.pop()
            identity = self._identity(element)
            if identity in seen:
                self.last_traversal_errors.append(f"cycle or duplicate skipped: {element.id}")
                continue
            if depth > max_depth:
                self.last_traversal_errors.append(f"maximum depth {max_depth} reached at {element.id}")
                continue
            seen.add(identity)
            result.append(element)
            try:
                children = self.get_children(element)
            except MSAAError as exc:
                self.last_traversal_errors.append(str(exc))
                continue
            if len(result) + len(stack) + len(children) > max_nodes:
                self.last_traversal_errors.append(f"maximum node limit {max_nodes} reached")
                children = children[: max(0, max_nodes - len(result) - len(stack))]
            stack.extend((child, depth + 1) for child in reversed(children))
        return result

    @staticmethod
    def _identity(element: MSAAElement) -> tuple[int, int, str]:
        """Use COM identity when available, retaining fake-tree IDs for tests."""
        interface = element.interface
        if interface is None:
            return (0, element.child_id, element.id)
        try:
            address = int(ctypes.cast(interface, ctypes.c_void_p).value or 0)
        except (TypeError, ValueError):
            address = 0
        return (address, element.child_id, "")

    def invoke(self, element: MSAAElement) -> None:
        try:
            element.interface.accDoDefaultAction(_child(element.child_id))
        except Exception as exc:
            raise MSAAActionError(f"MSAA default action failed for {element.id}: {exc}") from exc

    def focus(self, element: MSAAElement) -> None:
        try:
            element.interface.accSelect(0x1, _child(element.child_id))
        except Exception as exc:
            raise MSAAActionError(f"MSAA focus failed for {element.id}: {exc}") from exc

    def select(self, element: MSAAElement) -> None:
        try:
            element.interface.accSelect(0x2, _child(element.child_id))
        except Exception as exc:
            raise MSAAActionError(f"MSAA select failed for {element.id}: {exc}") from exc

    def set_value(self, element: MSAAElement, value: str) -> None:
        try:
            element.interface.put_accValue(_child(element.child_id), BSTR(value))
        except Exception as exc:
            raise MSAAActionError(f"MSAA set value failed for {element.id}: {exc}") from exc

    def inspect(self, window: MSAAWindow, *, max_depth: int = 32, max_nodes: int = 5000) -> list[AccessibilityNode]:
        nodes: list[AccessibilityNode] = []
        for element in self.walk(window.root, max_depth=max_depth, max_nodes=max_nodes):
            try:
                children = self.get_children(element)
                child_ids = [child.id for child in children]
            except MSAAError as exc:
                children = []
                child_ids = []
                error = str(exc)
            else:
                error = None
            nodes.append(AccessibilityNode(element.id, element.parent_id, self.get_name(element), self.get_role(element), self.get_state(element), self.get_value(element), self.get_description(element), element.hwnd, element.child_id, child_ids, self.get_default_action(element), len(children), error))
        if self.last_traversal_errors and nodes:
            nodes[-1].traversal_error = "; ".join(self.last_traversal_errors)
        return nodes

    def _from_hwnd(self, hwnd: int, *, objid: int = -4) -> IAccessible:
        pointer = ctypes.c_void_p()
        iid = IAccessible._iid_
        hr = self._oleacc.AccessibleObjectFromWindow(hwnd, objid, ctypes.byref(iid), ctypes.byref(pointer))
        if hr != 0 or not pointer.value:
            raise MSAANotSupported(f"IAccessible unavailable for hwnd={hwnd}, HRESULT=0x{hr & 0xffffffff:x}")
        return cast(pointer, POINTER(IAccessible))

    @staticmethod
    def _bstr(element: MSAAElement, method: str) -> str | None:
        try:
            value = getattr(element.interface, method)(_child(element.child_id))
            return str(value) if value else None
        except Exception:
            return None

    @staticmethod
    def _title(hwnd: int) -> str:
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    @staticmethod
    def _pid(hwnd: int) -> int:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value)
