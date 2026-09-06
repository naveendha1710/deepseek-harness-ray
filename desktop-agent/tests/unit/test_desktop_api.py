from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from desktop_agent.core.desktop_api import DesktopAPI
from desktop_agent.core.elements import Bounds, ElementMetadata, ElementRef, Snapshot
from desktop_agent.core.errors import AmbiguousError, StaleReferenceError
from desktop_agent.core.results import DesktopResult, DesktopStatus
from desktop_agent.core.selectors import ElementSelector
from desktop_agent.core.snapshots import make_snapshot


def metadata(name="Editor", hwnd=10):
    return ElementMetadata(role="edit", name=name, value="text", bounds=Bounds(1, 2, 11, 22), enabled=True, visible=True, provider="uia", source="uia", hwnd=hwnd, pid=20, control_type="Edit", provider_metadata={"automation_id": "editor"})


def test_bounds_and_metadata_preserve_provider_data():
    value = metadata().to_dict()
    assert value["bounds"]["right"] - value["bounds"]["left"] == 10
    assert value["provider_metadata"]["automation_id"] == "editor"


def test_element_ref_and_snapshot_round_trip():
    snapshot = make_snapshot([metadata()])
    restored = Snapshot.from_dict(json.loads(json.dumps(snapshot.to_dict())))
    assert restored == snapshot
    assert ElementRef.from_dict(snapshot.elements[0].to_dict()) == snapshot.elements[0]


def test_deterministic_snapshot_ids_and_refs():
    first = make_snapshot([metadata(), metadata("Button", 11)])
    second = make_snapshot([metadata("Button", 11), metadata()])
    assert first == second


def test_find_rejects_ambiguous_selector():
    api = DesktopAPI()
    api.snapshot([metadata("same", 10), metadata("same", 11)])
    try:
        api.find(ElementSelector(name="same"))
    except AmbiguousError:
        pass
    else:
        raise AssertionError("ambiguous selector was accepted")


def test_stale_reference_is_rejected():
    api = DesktopAPI()
    old = api.snapshot([metadata()]).elements[0]
    api.snapshot([metadata("changed")])
    try:
        api.inspect(old)
    except StaleReferenceError:
        pass
    else:
        raise AssertionError("stale reference was accepted")


def test_result_and_status_serialization():
    result = DesktopResult.success({"ok": True})
    restored = DesktopResult.from_dict(result.to_dict())
    assert restored.status == DesktopStatus.SUCCESS
    assert restored.result == {"ok": True}


def test_provider_neutral_action_is_explicitly_unsupported():
    api = DesktopAPI()
    element = api.snapshot([metadata()]).elements[0]
    assert api.click(element).status == DesktopStatus.UNSUPPORTED


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test()
    print("D6B.0 API TESTS: PASS (7/7)")
