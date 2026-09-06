from __future__ import annotations

from typing import Any, Protocol

from .elements import ElementMetadata, ElementRef, Snapshot
from .errors import AmbiguousError, NotFoundError, StaleReferenceError
from .results import DesktopResult, DesktopStatus
from .selectors import ElementSelector
from .snapshots import make_snapshot


class ProviderCapability(Protocol):
    def can(self, action: str, element: ElementRef | None = None) -> bool: ...


class DesktopAPI:
    """Provider-neutral canonical API; provider selection is explicit and external."""

    def __init__(self, provider: ProviderCapability | None = None):
        self.provider = provider
        self._current: Snapshot | None = None

    def snapshot(self, elements: list[ElementMetadata]) -> Snapshot:
        self._current = make_snapshot(elements)
        return self._current

    def capture(self) -> Snapshot:
        """Capture a snapshot through the explicitly supplied provider adapter."""
        if self.provider is None or not hasattr(self.provider, "snapshot_elements"):
            raise NotFoundError("No explicit provider can capture a snapshot")
        return self.snapshot(self.provider.snapshot_elements())

    def find(self, selector: ElementSelector, snapshot: Snapshot | None = None) -> ElementRef:
        source = snapshot or self._current
        if source is None:
            raise NotFoundError("No snapshot is available")
        matches = [element for element in source.elements if selector.matches(element)]
        if not matches:
            raise NotFoundError(f"No element matched selector: {selector}")
        if len(matches) > 1:
            raise AmbiguousError(f"Selector matched {len(matches)} elements")
        return matches[0]

    def inspect(self, element: ElementRef) -> ElementMetadata:
        self._check_ref(element)
        return element.metadata

    def _check_ref(self, element: ElementRef) -> None:
        if self._current is None:
            raise StaleReferenceError("No current snapshot can validate the reference")
        current = next((item for item in self._current.elements if item.ref == element.ref), None)
        if current is None or current.identity != element.identity:
            raise StaleReferenceError(f"Reference {element.ref!r} is stale")

    def _execute(self, action: str, element: ElementRef, parameters: dict[str, Any] | None = None) -> DesktopResult:
        self._check_ref(element)
        if self.provider is None or not self.provider.can(action, None):
            return DesktopResult(DesktopStatus.UNSUPPORTED, error=f"No explicit provider supports {action}")
        try:
            return DesktopResult.success(self.provider.execute(action, element, parameters or {}))
        except Exception as exc:
            return DesktopResult(DesktopStatus.ACTION_FAILED, error=repr(exc))

    def screenshot(self) -> DesktopResult: return DesktopResult(DesktopStatus.UNSUPPORTED, error="Screenshot requires an explicit provider adapter")
    def read(self, element: ElementRef) -> DesktopResult: return self._execute("read", element)
    def click(self, element: ElementRef) -> DesktopResult: return self._execute("click", element)
    def type(self, element: ElementRef, text: str) -> DesktopResult: return self._execute("type", element, {"text": text})
    def invoke(self, element: ElementRef) -> DesktopResult: return self._execute("invoke", element)
    def select(self, element: ElementRef, value: Any) -> DesktopResult: return self._execute("select", element, {"value": value})
    def scroll(self, element: ElementRef, delta: int) -> DesktopResult: return self._execute("scroll", element, {"amount": delta})
    def wait_for(self, selector: ElementSelector) -> DesktopResult: return DesktopResult(DesktopStatus.UNSUPPORTED, error="wait_for requires an explicit observation loop")
    def assert_state(self, element: ElementRef, expected: Any) -> DesktopResult:
        actual = self.read(element)
        if actual.status != DesktopStatus.SUCCESS:
            return actual
        verified = actual.result == expected or actual.result.get("text") == expected if isinstance(actual.result, dict) else actual.result == expected
        return DesktopResult.success(actual.result, verification=verified) if verified else DesktopResult(DesktopStatus.VERIFICATION_FAILED, result=actual.result, verification=False, error="Expected state did not match")


# Neutral facade for callers that want the canonical `desktop.*` spelling.
desktop = DesktopAPI()
