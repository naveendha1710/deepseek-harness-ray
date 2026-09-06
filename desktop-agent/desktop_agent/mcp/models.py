from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class MCPStatus(str, Enum):
    SUCCESS = "SUCCESS"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
    UNSUPPORTED = "UNSUPPORTED"
    ACTION_FAILED = "ACTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    STALE_REFERENCE = "STALE_REFERENCE"


@dataclass
class MCPResult:
    request_id: str
    provider: str
    tool: str
    target: Any
    action: str | None
    status: MCPStatus
    duration_ms: float
    verification: Any = None
    result: Any = None
    error: str | None = None

    @classmethod
    def start(cls, provider: str, tool: str, target: Any, action: str | None):
        return cls(str(uuid.uuid4()), provider, tool, target, action, MCPStatus.SUCCESS, 0.0)

    def finish(self, status: MCPStatus, *, result: Any = None, verification: Any = None, error: str | None = None, started: float):
        self.status = status
        self.result = result
        self.verification = verification
        self.error = error
        self.duration_ms = round((time.monotonic() - started) * 1000, 3)
        return asdict(self) | {"status": self.status.value}
