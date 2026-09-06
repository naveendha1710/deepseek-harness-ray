from __future__ import annotations

from pathlib import Path

from desktop_agent.fixtures.uia import FixtureTarget


ROOT = Path(__file__).resolve().parents[2]
MSAA_FIXTURE_EXE = ROOT / "fixtures" / "d3c-fixture" / "bin" / "Release" / "net8.0-windows" / "D3CUiaFixture.exe"
NATIVE_MSAA_FIXTURE_EXE = ROOT / "fixtures" / "d4-win32-fixture" / "bin" / "Release" / "net8.0-windows" / "D4Win32Fixture.exe"

WINFORMS_D4_FIXTURE_TARGET = FixtureTarget(
    app="D4 WinForms Provider-Limitation Fixture",
    executable="D3CUiaFixture.exe",
    command=(str(MSAA_FIXTURE_EXE),),
    title_re=r"^D3C UIA Fixture(?: Window)?$",
    startup_timeout=10.0,
    auto_launch=True,
    cleanup_policy="terminate_owned",
    selection_policy="require_unique",
)

D4_FIXTURE_TARGET = FixtureTarget(
    app="D4 Native Win32 MSAA Fixture",
    executable="D4Win32Fixture.exe",
    command=(str(NATIVE_MSAA_FIXTURE_EXE),),
    # This Windows/.NET host exposes the native caption as the first UTF-16 character.
    title_re=r"^D$",
    startup_timeout=10.0,
    auto_launch=True,
    cleanup_policy="terminate_owned",
    selection_policy="require_unique",
)
