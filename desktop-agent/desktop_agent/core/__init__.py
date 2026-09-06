"""Shared desktop-agent models and action results."""

from .desktop_api import DesktopAPI, desktop
from .elements import Bounds, ElementMetadata, ElementRef, Snapshot
from .results import DesktopResult, DesktopStatus

__all__ = ["Bounds", "DesktopAPI", "DesktopResult", "DesktopStatus", "ElementMetadata", "ElementRef", "Snapshot", "desktop"]
