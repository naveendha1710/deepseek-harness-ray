from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .elements import ElementMetadata, ElementRef, Snapshot, stable_identity


def make_snapshot(elements: Iterable[ElementMetadata]) -> Snapshot:
    metadata = sorted(list(elements), key=lambda item: (stable_identity(item), item.name or "", item.role or ""))
    digest = hashlib.sha256(json.dumps([item.to_dict() for item in metadata], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]
    refs = tuple(ElementRef(digest, f"e-{index:04d}-{stable_identity(item)[:12]}", item) for index, item in enumerate(metadata))
    return Snapshot(digest, refs)
