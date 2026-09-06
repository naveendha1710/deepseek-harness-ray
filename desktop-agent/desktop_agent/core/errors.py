from __future__ import annotations


class DesktopError(RuntimeError):
    """Base error for canonical desktop API operations."""


class NotFoundError(DesktopError):
    """No element matched a deterministic selector."""


class AmbiguousError(DesktopError):
    """A selector matched more than one element."""


class StaleReferenceError(DesktopError):
    """An element reference cannot be proven valid in the current snapshot."""


class UnsupportedError(DesktopError):
    """The explicitly selected provider does not support an operation."""


class InvalidArgumentError(DesktopError, ValueError):
    """A canonical API argument is invalid."""
