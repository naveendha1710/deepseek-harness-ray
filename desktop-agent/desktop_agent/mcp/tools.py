from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from desktop_agent.core.desktop_api import DesktopAPI
from desktop_agent.core.elements import ElementRef
from desktop_agent.core.errors import AmbiguousError, NotFoundError, StaleReferenceError
from desktop_agent.core.provider_adapters import UIAProviderAdapter, Win32ProviderAdapter
from desktop_agent.core.results import DesktopStatus
from desktop_agent.core.selectors import ElementSelector
from desktop_agent.providers import pyautogui

from .models import MCPResult, MCPStatus


CANONICAL_TOOLS = (
    "desktop_snapshot", "desktop_find", "desktop_inspect", "desktop_click", "desktop_type",
    "desktop_read", "desktop_invoke", "desktop_select", "desktop_scroll", "desktop_screenshot",
    "desktop_wait_for", "desktop_assert",
)
_APIS: dict[str, DesktopAPI] = {}


def tool_definitions() -> list[dict[str, Any]]:
    return [{"name": name, "description": f"Canonical desktop operation: {name}", "inputSchema": {"type": "object", "additionalProperties": True}} for name in CANONICAL_TOOLS]


def _adapter(provider_hint: str | None):
    if provider_hint in (None, "uia"):
        return UIAProviderAdapter()
    if provider_hint == "win32":
        return Win32ProviderAdapter()
    if provider_hint in {"msaa", "pyautogui"}:
        raise ValueError(f"Provider hint {provider_hint!r} is not yet supported by the canonical execution adapter")
    raise ValueError(f"Invalid provider_hint: {provider_hint!r}")


def _api(arguments: dict[str, Any]) -> DesktopAPI:
    hint = arguments.get("provider_hint") or "uia"
    if hint not in _APIS:
        _APIS[hint] = DesktopAPI(_adapter(hint))
    return _APIS[hint]


def _result(tool: str, target: Any, action: str | None, operation) -> dict[str, Any]:
    started = time.monotonic()
    request = MCPResult.start("canonical", tool, target, action)
    try:
        return request.finish(MCPStatus.SUCCESS, result=operation(), verification=True, started=started)
    except AmbiguousError as exc:
        return request.finish(MCPStatus.AMBIGUOUS, error=str(exc), started=started)
    except (NotFoundError,) as exc:
        return request.finish(MCPStatus.TARGET_NOT_FOUND, error=str(exc), started=started)
    except StaleReferenceError as exc:
        return request.finish(MCPStatus.STALE_REFERENCE, error=str(exc), started=started)
    except TimeoutError as exc:
        return request.finish(MCPStatus.TIMEOUT, error=str(exc), started=started)
    except (ValueError, KeyError, TypeError) as exc:
        return request.finish(MCPStatus.INVALID_ARGUMENT, error=str(exc), started=started)
    except Exception as exc:
        return request.finish(MCPStatus.PROVIDER_ERROR, error=repr(exc), started=started)


def _ref(arguments: dict[str, Any]) -> ElementRef:
    return ElementRef.from_dict(arguments["element_ref"])


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in CANONICAL_TOOLS:
        raise ValueError(f"Unknown canonical desktop MCP tool: {name}")
    if name == "desktop_snapshot":
        return _result(name, {}, None, lambda: _snapshot(arguments))
    if name == "desktop_find":
        return _result(name, arguments.get("selector", {}), None, lambda: _find(arguments))
    if name == "desktop_inspect":
        return _result(name, arguments.get("element_ref"), "inspect", lambda: _api(arguments).inspect(_ref(arguments)).to_dict())
    if name == "desktop_screenshot":
        return _result(name, {}, "screenshot", lambda: pyautogui.screenshot(arguments.get("path")))
    if name == "desktop_wait_for":
        return _result(name, arguments.get("selector", {}), "wait_for", lambda: _wait_for(arguments))
    if name == "desktop_assert":
        return _result(name, arguments.get("element_ref"), "assert_state", lambda: _api(arguments).assert_state(_ref(arguments), arguments.get("expected_state")).to_dict())
    action = {"desktop_click": "click", "desktop_type": "type", "desktop_read": "read", "desktop_invoke": "invoke", "desktop_select": "select", "desktop_scroll": "scroll"}[name]
    return _result(name, arguments.get("element_ref"), action, lambda: _action(arguments, action))


def _snapshot(arguments):
    snapshot = _api(arguments).capture()
    return snapshot.to_dict()


def _find(arguments):
    api = _api(arguments)
    snapshot = api.capture()
    selector = ElementSelector(**arguments.get("selector", {}))
    matches = [element for element in snapshot.elements if selector.matches(element)]
    if not matches: raise NotFoundError(f"No element matched selector {selector}")
    if len(matches) > 1: raise AmbiguousError(f"Selector matched {len(matches)} elements")
    return {"matches": [item.to_dict() for item in matches], "count": len(matches), "snapshot_id": snapshot.snapshot_id, "status": "SUCCESS"}


def _action(arguments, action):
    api = _api(arguments)
    element = _ref(arguments)
    result = getattr(api, action)(element, arguments.get("value")) if action == "select" else getattr(api, action)(element, arguments.get("amount", 0)) if action == "scroll" else getattr(api, action)(element, arguments["text"]) if action == "type" else getattr(api, action)(element)
    return {"snapshot_id": element.snapshot_id, "target_ref": element.ref, "action": action, "before": None, "operation": action, "after": result.result, "expected": None, "verification": result.verification, "status": result.status.value, "duration": result.duration_ms, "error": result.error}


def _wait_for(arguments):
    deadline = time.monotonic() + float(arguments.get("timeout", 5.0))
    while time.monotonic() < deadline:
        try:
            return _find(arguments)
        except (NotFoundError, AmbiguousError):
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
    raise TimeoutError(f"Timed out waiting for selector {arguments.get('selector')}")
