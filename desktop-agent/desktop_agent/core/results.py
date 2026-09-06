from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DesktopStatus(str, Enum):
    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    STALE_REFERENCE = "STALE_REFERENCE"
    UNSUPPORTED = "UNSUPPORTED"
    ACTION_FAILED = "ACTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"


@dataclass
class DesktopResult:
    status: DesktopStatus
    result: Any = None
    verification: Any = None
    error: str | None = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    duration_ms: float = 0.0

    @classmethod
    def success(cls, result: Any = None, verification: Any = True) -> "DesktopResult":
        return cls(DesktopStatus.SUCCESS, result=result, verification=verification)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "result": self.result,
            "verification": self.verification,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DesktopResult":
        return cls(DesktopStatus(value["status"]), value.get("result"), value.get("verification"), value.get("error"), str(value["request_id"]), float(value.get("duration_ms", 0)))


def timed(operation):
    started = time.monotonic()
    try:
        return DesktopResult.success(operation())
    finally:
        _ = time.monotonic() - started
