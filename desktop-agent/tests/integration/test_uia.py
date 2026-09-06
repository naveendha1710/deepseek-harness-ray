from __future__ import annotations

import sys
import traceback
import re
from pathlib import Path
from uuid import uuid4


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from desktop_agent.providers.uia import UIAAdapter, UIAError, WindowCandidate
from desktop_agent.fixtures.uia import FIXTURE_TARGETS, FixtureStatus, UIAFixtureManager


NOTEPAD_TITLE_RE = r".*Notepad.*"
TEST_TIMEOUT = 10.0
REPEATED_ITERATIONS = 5
TARGET_HANDLE: int | None = None


class FixtureUnavailable(RuntimeError):
    """Raised when the live desktop does not provide the required fixture."""


def _adapter() -> UIAAdapter:
    return UIAAdapter(timeout=TEST_TIMEOUT)


def _candidate(title: str, pid: int, handle: int) -> WindowCandidate:
    return WindowCandidate(
        title=title,
        pid=pid,
        handle=handle,
        rect=None,
        visible=True,
        enabled=True,
    )


def _stub_adapter(candidates: list[WindowCandidate]) -> UIAAdapter:
    adapter = UIAAdapter.__new__(UIAAdapter)
    adapter.timeout = TEST_TIMEOUT

    def list_candidates(title_re: str) -> list[WindowCandidate]:
        return [candidate for candidate in candidates if re.search(title_re, candidate.title)]

    selected_handles: list[int] = []

    class Spec:
        def exists(self, timeout: float) -> bool:
            return True

    adapter.list_window_candidates = list_candidates
    adapter.desktop = type(
        "DesktopStub",
        (),
        {"window": lambda self, **kwargs: (selected_handles.append(kwargs["handle"]) or Spec())},
    )()
    adapter._selected_handles = selected_handles
    return adapter


def test_unit_zero_candidates():
    adapter = _stub_adapter([])
    try:
        adapter.window_spec(".*Notepad.*")
    except UIAError as exc:
        assert "No window matched" in str(exc)
    else:
        raise AssertionError("Zero candidates unexpectedly selected a window")


def test_unit_exactly_one_candidate():
    adapter = _stub_adapter([_candidate("Target - Notepad", 10, 101)])
    adapter.window_spec(".*Notepad.*")
    assert adapter._selected_handles == [101]


def test_unit_multiple_candidates_rejected():
    adapter = _stub_adapter(
        [_candidate("A - Notepad", 10, 101), _candidate("B - Notepad", 10, 102)]
    )
    try:
        adapter.window_spec(".*Notepad.*")
    except UIAError as exc:
        assert "Ambiguous window selector" in str(exc)
        assert "handle=101" in str(exc)
        assert "handle=102" in str(exc)
    else:
        raise AssertionError("Multiple candidates unexpectedly selected a window")


def test_unit_handle_selection():
    adapter = _stub_adapter([_candidate("A - Notepad", 10, 101)])
    adapter.window_spec_by_handle(909)
    assert adapter._selected_handles == [909]


def test_unit_pid_selection():
    adapter = _stub_adapter(
        [_candidate("A - Notepad", 10, 101), _candidate("B - Notepad", 11, 102)]
    )
    adapter.window_spec_by_pid(11)
    assert adapter._selected_handles == [102]


def test_unit_pid_title_selection():
    adapter = _stub_adapter(
        [_candidate("Target - Notepad", 10, 101), _candidate("Other - Notepad", 10, 102)]
    )
    adapter.window_spec_by_pid(10, title_re=r"^Target")
    assert adapter._selected_handles == [101]


def test_unit_invalid_handle():
    adapter = UIAAdapter.__new__(UIAAdapter)
    adapter.timeout = TEST_TIMEOUT

    class MissingSpec:
        def exists(self, timeout: float) -> bool:
            return False

    adapter.desktop = type("DesktopStub", (), {"window": lambda self, **kwargs: MissingSpec()})()
    try:
        adapter.window_spec_by_handle(404)
    except UIAError as exc:
        assert "handle=404" in str(exc)
    else:
        raise AssertionError("Invalid handle unexpectedly resolved")


def test_unit_control_name_selector_is_explicit():
    adapter = UIAAdapter.__new__(UIAAdapter)
    adapter.timeout = TEST_TIMEOUT
    observed: list[dict] = []

    class ControlSpec:
        def exists(self, timeout: float) -> bool:
            return True

        def wrapper_object(self):
            return object()

    class WindowSpec:
        def child_window(self, **criteria):
            observed.append(criteria)
            return ControlSpec()

    adapter.find_control(WindowSpec(), name="Text editor", control_type="Document")
    assert observed[0]["control_type"] == "Document"
    assert "predicate_func" in observed[0]
    assert "title" not in observed[0]
    assert observed[0]["predicate_func"](
        type("ElementInfo", (), {"name": "Text editor"})()
    )

    adapter.find_control(WindowSpec(), title="Text editor", control_type="Document")
    assert observed[1]["title"] == "Text editor"
    assert "predicate_func" not in observed[1]


def _window_summary(window) -> str:
    rect = None
    try:
        rect_obj = window.rectangle()
        rect = (
            rect_obj.left,
            rect_obj.top,
            rect_obj.right,
            rect_obj.bottom,
        )
    except Exception:
        rect = None
    return (
        f"title={window.window_text()!r} pid={window.process_id()} "
        f"visible={window.is_visible()} enabled={window.is_enabled()} "
        f"rect={rect}"
    )


def _control_auto_id(control) -> str | None:
    return (
        getattr(control.element_info, "automation_id", None)
        or getattr(control.element_info, "auto_id", None)
        or None
    )


def _control_summary(control) -> str:
    return (
        f"type={control.element_info.control_type!r} "
        f"name={control.element_info.name!r} "
        f"auto_id={_control_auto_id(control)!r} "
        f"iface_text={getattr(control, 'iface_text', None) is not None}"
    )


def _control_identity(control):
    """Return the UIA runtime identity used to compare resolved controls."""

    runtime_id = getattr(control.element_info, "runtime_id", None)
    if not runtime_id:
        raise AssertionError("UIA control has no runtime identity")
    return tuple(runtime_id)


def _target_window_spec(adapter: UIAAdapter):
    if TARGET_HANDLE is None:
        raise AssertionError("Target window was not selected during discovery")
    return adapter.window_spec_by_handle(TARGET_HANDLE)


def _document_with_selectors(adapter: UIAAdapter):
    window_spec = _target_window_spec(adapter)
    document = adapter.find_control(window_spec, control_type="Document")
    return window_spec, document


def _clear_document(adapter: UIAAdapter, document) -> None:
    adapter.press(document, "^a{DEL}")


def _write_marker(adapter: UIAAdapter, document, marker: str) -> None:
    _clear_document(adapter, document)
    adapter.type_text(document, marker)


def _read_text_or_fail(marker: str, adapter: UIAAdapter, document) -> str:
    try:
        text = adapter.read_text_pattern(document)
    except UIAError as exc:
        cause = repr(exc.__cause__) if exc.__cause__ is not None else "<none>"
        raise AssertionError(
            f"Text Pattern read failed for {marker!r}: {exc} | cause={cause}"
        ) from exc

    print(f"READ LENGTH: {len(text)}")
    print(f"READ TAIL: {text[-200:]!r}")
    assert marker in text, (
        f"Marker {marker!r} was not present in Text Pattern output. "
        f"Tail={text[-200:]!r}"
    )
    return text


def test_01_window_discovery():
    global TARGET_HANDLE

    adapter = _adapter()
    candidates = adapter.list_window_candidates(NOTEPAD_TITLE_RE)

    print("TEST 1: WINDOW DISCOVERY")
    print(f"WINDOW COUNT: {len(candidates)}")
    for index, candidate in enumerate(candidates):
        print(
            f"WINDOW[{index}]: title={candidate.title!r} pid={candidate.pid} "
            f"handle={candidate.handle} rect={candidate.rect} "
            f"visible={candidate.visible} enabled={candidate.enabled}"
        )

    assert candidates, "No visible Notepad window found"

    # Native handles are unique UIA identities; sorting makes the test choice reproducible.
    target = sorted(candidates, key=lambda candidate: candidate.handle)[0]
    TARGET_HANDLE = target.handle
    window = adapter.window_spec_by_handle(TARGET_HANDLE).wrapper_object()
    print(f"FOUND WINDOW WRAPPER: {type(window).__name__}")
    print(f"FOUND WINDOW: {_window_summary(window)}")

    print(
        "INSPECT WINDOW: "
        f"title={target.title!r} pid={target.pid} visible={target.visible} "
        f"enabled={target.enabled} rect={target.rect}"
    )

    assert "Notepad" in target.title
    assert target.pid > 0
    assert target.visible is True
    assert target.enabled is True
    assert target.rect is None or len(target.rect) == 4


def test_02_control_discovery():
    adapter = _adapter()
    window_spec, document = _document_with_selectors(adapter)

    print("TEST 2: CONTROL DISCOVERY")
    print(f"WINDOW SPEC TYPE: {type(window_spec).__name__}")
    print(f"DOCUMENT WRAPPER TYPE: {type(document).__name__}")
    print(f"DOCUMENT: {_control_summary(document)}")

    assert type(window_spec).__name__ == "WindowSpecification"
    assert document.element_info.control_type == "Document"
    assert document.element_info.name is not None
    assert document.element_info.name != ""
    assert getattr(document, "iface_text", None) is not None


def test_03_focus():
    adapter = _adapter()
    _, document = _document_with_selectors(adapter)

    print("TEST 3: FOCUS")
    print(f"DOCUMENT BEFORE FOCUS: {_control_summary(document)}")
    adapter.focus(document)
    print("FOCUS RESULT: PASS")


def test_04_write():
    adapter = _adapter()
    _, document = _document_with_selectors(adapter)
    marker = f"D3_UIA_WRITE_TEST_2026_{uuid4().hex[:8]}"

    print("TEST 4: WRITE")
    print(f"MARKER: {marker}")
    _write_marker(adapter, document, marker)
    print("WRITE RESULT: PASS")


def test_05_read():
    adapter = _adapter()
    _, document = _document_with_selectors(adapter)
    marker = f"D3_UIA_WRITE_TEST_2026_{uuid4().hex[:8]}"

    print("TEST 5: READ")
    print(f"MARKER: {marker}")
    _write_marker(adapter, document, marker)
    text = _read_text_or_fail(marker, adapter, document)
    print("READ RESULT: PASS")
    print(f"READ VERIFIED MARKER: {marker in text}")


def test_06_repeated_stability():
    adapter = _adapter()
    _, document = _document_with_selectors(adapter)

    print("TEST 6: REPEATED STABILITY")
    for iteration in range(1, REPEATED_ITERATIONS + 1):
        marker = f"D3_UIA_WRITE_TEST_2026_REPEAT_{iteration}_{uuid4().hex[:8]}"
        print(f"ITERATION {iteration}: MARKER={marker}")
        _write_marker(adapter, document, marker)
        text = _read_text_or_fail(marker, adapter, document)
        print(f"ITERATION {iteration}: PASS (len={len(text)})")


def test_07_selector_stability():
    adapter = _adapter()
    window_spec, document = _document_with_selectors(adapter)
    document_name = document.element_info.name
    document_auto_id = _control_auto_id(document)

    print("TEST 7: SELECTOR STABILITY")
    print(f"BASE DOCUMENT: {_control_summary(document)}")
    base_identity = _control_identity(document)
    print(f"BASE UIA RUNTIME ID: {base_identity}")

    doc_by_type = adapter.find_control(window_spec, control_type="Document")
    print(f"BY TYPE: {_control_summary(doc_by_type)}")
    assert doc_by_type.element_info.control_type == "Document"
    assert _control_identity(doc_by_type) == base_identity

    if document_name:
        doc_by_name = adapter.find_control(
            window_spec,
            name=document_name,
            control_type="Document",
        )
        print(f"BY UIA NAME: {_control_summary(doc_by_name)}")
        assert doc_by_name.element_info.control_type == "Document"
        assert doc_by_name.element_info.name == document_name
        assert _control_identity(doc_by_name) == base_identity

        doc_by_combined = adapter.find_control(
            window_spec,
            name=document_name,
            control_type="Document",
        )
        print(f"BY UIA NAME + TYPE: {_control_summary(doc_by_combined)}")
        assert _control_identity(doc_by_combined) == base_identity

        try:
            adapter.find_control(
                window_spec,
                title=document_name,
                control_type="Document",
            )
        except UIAError as exc:
            print(f"BY TITLE REGRESSION: REJECTED ({exc})")
        else:
            raise AssertionError(
                "title= unexpectedly matched the UIA Name-only Document control"
            )
    else:
        print("BY UIA NAME: SKIPPED (empty control name)")
        print("BY UIA NAME + TYPE: SKIPPED (empty control name)")
        print("BY TITLE REGRESSION: SKIPPED (empty control name)")

    if document_auto_id:
        doc_by_auto_id = adapter.find_control(
            window_spec,
            auto_id=document_auto_id,
            control_type="Document",
        )
        print(f"BY AUTO_ID: {_control_summary(doc_by_auto_id)}")
        assert doc_by_auto_id.element_info.control_type == "Document"
        assert _control_auto_id(doc_by_auto_id) == document_auto_id
        assert _control_identity(doc_by_auto_id) == base_identity
    else:
        print("BY AUTO_ID: SKIPPED (empty automation id)")


def test_08_no_fallback_verification():
    print("TEST 8: NO FALLBACK VERIFICATION")
    imported = [
        name
        for name in sys.modules
        if name == "pyautogui" or name.startswith("pyautogui.")
    ]
    print(f"PYAUTOGUI IMPORTS: {imported}")
    assert imported == []


def test_09_ambiguous_window_is_rejected():
    adapter = _adapter()
    candidates = adapter.list_window_candidates(NOTEPAD_TITLE_RE)

    print("TEST 9: AMBIGUOUS WINDOW REJECTION")
    print(f"MATCHING CANDIDATES: {len(candidates)}")
    if len(candidates) < 2:
        print("AMBIGUITY REGRESSION: SKIPPED (fewer than two candidates)")
        return

    try:
        adapter.window_spec(NOTEPAD_TITLE_RE)
    except UIAError as exc:
        print(f"AMBIGUITY ERROR: {exc}")
    else:
        raise AssertionError("Broad Notepad selector unexpectedly selected a window")


def _run_tests(tests) -> int:
    failures = 0
    for test in tests:
        print()
        print(f"RUNNING: {test.__name__}")
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f"RESULT: FAIL - {exc}")
            traceback.print_exc()
        else:
            print("RESULT: PASS")
    return failures


def run_suite() -> int:
    unit_tests = [
        test_unit_zero_candidates,
        test_unit_exactly_one_candidate,
        test_unit_multiple_candidates_rejected,
        test_unit_handle_selection,
        test_unit_pid_selection,
        test_unit_pid_title_selection,
        test_unit_invalid_handle,
        test_unit_control_name_selector_is_explicit,
    ]
    integration_tests = [
        test_01_window_discovery,
        test_02_control_discovery,
        test_03_focus,
        test_04_write,
        test_05_read,
        test_06_repeated_stability,
        test_07_selector_stability,
        test_08_no_fallback_verification,
        test_09_ambiguous_window_is_rejected,
    ]

    print("================================")
    print("D3 UIA ADAPTER TEST SUITE")
    print("================================")

    print()
    print("UNIT/SELECTOR TESTS:")
    unit_failures = _run_tests(unit_tests)
    print(f"UNIT/SELECTOR RESULT: {'PASS' if unit_failures == 0 else 'FAIL'}")

    print()
    print("REAL UIA INTEGRATION:")
    fixture_adapter = _adapter()
    fixtures = UIAFixtureManager(fixture_adapter)
    notepad_target = next(item for item in FIXTURE_TARGETS if item.app == "Notepad")
    fixture = fixtures.acquire(notepad_target, allow_launch=True)
    print(
        f"NOTEPAD FIXTURE: status={fixture.status.value} command={fixture.command} "
        f"launched_pid={fixture.launched_pid} elapsed={fixture.elapsed_seconds:.3f}s"
    )
    for index, candidate in enumerate(fixture.candidates):
        print(
            f"FIXTURE WINDOW[{index}]: title={candidate.title!r} pid={candidate.pid} "
            f"handle={candidate.handle} rect={candidate.rect} "
            f"visible={candidate.visible} enabled={candidate.enabled}"
        )

    try:
        if fixture.status == FixtureStatus.FIXTURE_UNAVAILABLE:
            print("BLOCKED - environment exposes zero Notepad windows")
            integration_failures = 0
            integration_blocked = True
        elif fixture.status != FixtureStatus.AVAILABLE:
            print(f"FIXTURE ERROR: {fixture.error}")
            integration_failures = 1
            integration_blocked = False
        else:
            global TARGET_HANDLE
            TARGET_HANDLE = fixture.selected.handle if fixture.selected else None
            integration_failures = _run_tests(integration_tests)
            integration_blocked = False
            print(
                "REAL UIA INTEGRATION RESULT: "
                f"{'PASS' if integration_failures == 0 else 'FAIL'}"
            )
    finally:
        fixtures.cleanup()

    print()
    print("================================")
    if unit_failures:
        result = "FAIL"
    elif integration_blocked:
        result = "BLOCKED"
    else:
        result = "PASS" if integration_failures == 0 else "FAIL"
    print(f"D3 REGRESSION: {result}")
    print(f"D3 RESULT: {result}")
    print("================================")
    return 1 if unit_failures or integration_failures else 0


if __name__ == "__main__":
    raise SystemExit(run_suite())
