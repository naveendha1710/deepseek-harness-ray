from __future__ import annotations

from dataclasses import asdict
from typing import Any

from desktop_agent.providers import uia, win32

from .elements import Bounds, ElementMetadata


class UIAProviderAdapter:
    """Explicit UIA adapter used by the canonical API; it never selects another provider."""

    provider = "uia"

    def can(self, action: str, element=None) -> bool:
        return action in {"read", "click", "type", "invoke", "select", "scroll", "inspect"}

    def snapshot_elements(self) -> list[ElementMetadata]:
        adapter = uia.UIAAdapter()
        elements: list[ElementMetadata] = []
        for candidate in adapter.list_window_candidates(r".*"):
            elements.append(self._window_metadata(candidate))
            try:
                spec = adapter.window_spec_by_handle(candidate.handle)
                for control in spec.descendants():
                    info = control.element_info
                    elements.append(ElementMetadata(
                        role=getattr(info, "control_type", None),
                        name=getattr(info, "name", None),
                        value=None,
                        bounds=self._bounds(control),
                        enabled=control.is_enabled(), visible=control.is_visible(),
                        provider="uia", source="uia", hwnd=getattr(info, "handle", None),
                        pid=getattr(info, "process_id", None), control_type=getattr(info, "control_type", None),
                        provider_metadata={"automation_id": getattr(info, "automation_id", None), "class_name": getattr(info, "class_name", None)},
                    ))
            except Exception:
                continue
        return elements

    def execute(self, action: str, element, parameters: dict[str, Any]) -> dict[str, Any]:
        adapter = uia.UIAAdapter()
        spec = adapter.window_spec_by_handle(element.metadata.hwnd)
        selector = {key: value for key, value in {"name": element.metadata.name, "control_type": element.metadata.control_type, "auto_id": element.metadata.provider_metadata.get("automation_id")}.items() if value}
        control = adapter.find_control(spec, **selector)
        if action == "read": return {"text": adapter.read_text_pattern(control)}
        if action == "click": adapter.click(control); return {"operation": "click"}
        if action == "type": adapter.type_text(control, str(parameters["text"])); return {"operation": "type"}
        if action == "invoke": adapter.click(control); return {"operation": "invoke"}
        raise uia.UIAError(f"UIA canonical action unsupported: {action}")

    @staticmethod
    def _bounds(control) -> Bounds | None:
        try:
            rect = control.rectangle()
            value = (rect.left, rect.top, rect.right, rect.bottom)
            return Bounds(*value) if value != (0, 0, 0, 0) else None
        except Exception:
            return None

    @staticmethod
    def _window_metadata(candidate) -> ElementMetadata:
        bounds = Bounds(*candidate.rect) if candidate.rect else None
        return ElementMetadata(role="window", name=candidate.title, bounds=bounds, enabled=candidate.enabled, visible=candidate.visible, provider="uia", source="uia", hwnd=candidate.handle, pid=candidate.pid, control_type="Window", provider_metadata={"class_name": candidate.class_name, "framework_id": candidate.framework_id})


class Win32ProviderAdapter:
    provider = "win32"

    def can(self, action: str, element=None) -> bool:
        return action in {"read", "type", "inspect"}

    def snapshot_elements(self) -> list[ElementMetadata]:
        return [ElementMetadata(role="window", name=item.title, bounds=Bounds(*item.rect) if item.rect else None, enabled=item.enabled, visible=item.visible, provider="win32", source="win32", hwnd=item.hwnd, pid=item.pid, provider_metadata={"class_name": item.class_name, "thread_id": item.thread_id, "process_name": item.process_name}) for item in win32.enumerate_windows()]

    def execute(self, action: str, element, parameters: dict[str, Any]) -> dict[str, Any]:
        if action == "read": return {"text": win32.get_control_text(element.metadata.hwnd)}
        if action == "type":
            win32.set_control_text(element.metadata.hwnd, str(parameters["text"]))
            return {"text": win32.get_control_text(element.metadata.hwnd)}
        raise win32.NativeUnsupported(f"Win32 canonical action unsupported: {action}")
