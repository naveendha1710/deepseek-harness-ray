# Desktop Agent

This directory contains the existing UIA, MSAA, Win32, and PyAutoGUI providers. It intentionally contains no Action Router, MCP integration, vision/OCR, or fallback policy.

## Layout

- `desktop_agent/providers/`: provider implementations
- `desktop_agent/fixtures/`: fixture managers
- `desktop_agent/matrix/`: UIA compatibility matrix
- `desktop_agent/core/`: shared action/result code
- `tests/unit/` and `tests/integration/`: validation suites
- `fixtures/`: executable .NET fixture projects
- `runners/`: live validation scripts
- `reports/`: generated JSON reports
- `artifacts/screenshots/`: generated screenshots

## Commands

Run from this directory:

```powershell
& ..\.desktop-agent-venv\Scripts\python.exe -m py_compile desktop_agent/providers/uia.py tests/integration/test_uia.py
& ..\.desktop-agent-venv\Scripts\python.exe tests/integration/test_uia.py
& ..\.desktop-agent-venv\Scripts\python.exe runners/run_uia_matrix.py
& ..\.desktop-agent-venv\Scripts\python.exe runners/run_d3c.py
& ..\.desktop-agent-venv\Scripts\python.exe runners/run_d4.py
& ..\.desktop-agent-venv\Scripts\python.exe runners/run_d5.py
& ..\.desktop-agent-venv\Scripts\python.exe runners/run_d6a.py
```

Unit tests are executable scripts under `tests/unit/`. Reports are written under `reports/`, and screenshots under `artifacts/screenshots/`.

Build fixtures from this directory:

```powershell
dotnet build .\fixtures\d3c-fixture\D3CUiaFixture.csproj -c Release
dotnet build .\fixtures\d4-win32-fixture\D4Win32Fixture.csproj -c Release
dotnet build .\fixtures\d6a-fixture\D6AFixture.csproj -c Release
```

This reorganization preserves deterministic targeting, strict ambiguity rejection, owned-fixture cleanup, and existing provider capability boundaries.

## D6B MCP Boundary

The standalone MCP adapter is in `desktop_agent/mcp/`. It exposes exactly:
`desktop_window_list`, `desktop_window_inspect`, `desktop_uia_find`,
`desktop_uia_action`, `desktop_msaa_find`, `desktop_msaa_action`,
`desktop_win32_action`, `desktop_pyautogui_action`, and `desktop_screenshot`.

Start it over stdio with:

```powershell
& ..\.desktop-agent-venv\Scripts\python.exe -m desktop_agent.mcp.server
```

The DSH MCP client registers these as `mcp__desktop__<tool>` when configured
with server name `desktop`. D6B does not add a DSH core or profile mutation;
the existing session MCP declaration is the integration point:
`command` must be the absolute venv Python path, `args` must be
`["-m", "desktop_agent.mcp.server"]`, and `cwd` must be this directory.
Provider identity is preserved and no automatic routing or fallback exists.
