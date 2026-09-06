from __future__ import annotations

from dataclasses import dataclass

from .elements import ElementRef


@dataclass(frozen=True)
class ElementSelector:
    ref: str | None = None
    provider: str | None = None
    role: str | None = None
    name: str | None = None
    control_type: str | None = None
    hwnd: int | None = None
    pid: int | None = None

    def matches(self, element: ElementRef) -> bool:
        metadata = element.metadata
        checks = {
            "provider": metadata.provider,
            "role": metadata.role,
            "name": metadata.name,
            "control_type": metadata.control_type,
            "hwnd": metadata.hwnd,
            "pid": metadata.pid,
        }
        for key, expected in checks.items():
            requested = getattr(self, key)
            if requested is not None and expected != requested:
                return False
        return self.ref is None or element.ref == self.ref
