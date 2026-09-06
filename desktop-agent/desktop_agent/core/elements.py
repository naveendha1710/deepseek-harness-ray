from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, order=True)
class Bounds:
    left: int
    top: int
    right: int
    bottom: int

    def __post_init__(self) -> None:
        if self.right < self.left or self.bottom < self.top:
            raise ValueError("Bounds right/bottom must not precede left/top")

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Bounds":
        return cls(*(int(value[key]) for key in ("left", "top", "right", "bottom")))


@dataclass(frozen=True)
class ElementMetadata:
    role: str | None = None
    name: str | None = None
    value: str | None = None
    bounds: Bounds | None = None
    enabled: bool | None = None
    visible: bool | None = None
    provider: str | None = None
    source: str | None = None
    hwnd: int | None = None
    pid: int | None = None
    control_type: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["bounds"] = self.bounds.to_dict() if self.bounds else None
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ElementMetadata":
        data = dict(value)
        if data.get("bounds") is not None:
            data["bounds"] = Bounds.from_dict(data["bounds"])
        return cls(**data)


def stable_identity(metadata: ElementMetadata) -> str:
    identity = {
        "provider": metadata.provider,
        "source": metadata.source,
        "hwnd": metadata.hwnd,
        "pid": metadata.pid,
        "role": metadata.role,
        "name": metadata.name,
        "control_type": metadata.control_type,
        "provider_metadata": metadata.provider_metadata,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class ElementRef:
    snapshot_id: str
    ref: str
    metadata: ElementMetadata

    @property
    def identity(self) -> str:
        return stable_identity(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "ref": self.ref, "metadata": self.metadata.to_dict()}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ElementRef":
        return cls(str(value["snapshot_id"]), str(value["ref"]), ElementMetadata.from_dict(value["metadata"]))


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    elements: tuple[ElementRef, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "elements": [element.to_dict() for element in self.elements]}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Snapshot":
        return cls(str(value["snapshot_id"]), tuple(ElementRef.from_dict(item) for item in value["elements"]))
