# Desktop UIA Adapter

Run the selector and live UIA checks with the desktop-agent virtual environment:

```powershell
& ..\.desktop-agent-venv\Scripts\python.exe -m py_compile uia.py test_uia.py
& ..\.desktop-agent-venv\Scripts\python.exe test_uia.py
```

The test suite never launches a GUI application. To deliberately provide two
Notepad candidates for the ambiguity regression, run these commands separately
before starting the suite:

```powershell
Start-Process notepad.exe
Start-Process notepad.exe
```

Confirm that both windows are visible and that the suite prints two distinct
native handles. The suite selects one handle for the end-to-end checks and
requires the broad `.*Notepad.*` selector to raise `UIAError`.
