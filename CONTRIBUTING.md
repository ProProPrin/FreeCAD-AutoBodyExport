# Contributing

Contributions and reproducible bug reports are welcome.

## Reporting issues

Use the issue templates and include:

- FreeCAD, addon, and operating-system versions;
- the affected export format and output mode;
- a minimal description of the relevant document structure;
- exact reproduction steps;
- FreeCAD Report view output with private paths removed.

Do not attach confidential CAD documents. Use a minimal replacement model.
Report security issues privately according to [SECURITY.md](SECURITY.md).

## Development setup

Install the repository in FreeCAD's user `Mod/AutoBodyExport` directory, or
link that directory to your checkout. Restart FreeCAD after changing addon
initialization code.

Runtime code lives in `freecad/AutoBodyExport/`. Top-level `Init.py` and
`InitGui.py` are compatibility entry points loaded by FreeCAD.

Match the existing style, keep changes focused, and add tests for behavior
changes. Do not weaken the global/document opt-in, unmanaged-file protection,
managed-path validation, or failure recovery.

## Checks

Run release validation:

```powershell
python tests\validate_release.py
```

Run Ruff when available:

```powershell
ruff check .
ruff format --check .
```

Run tests with both supported FreeCAD lines:

```powershell
$env:AUTOBODYEXPORT_TEST_TMP = "C:\tmp\autobodyexport-tests"
& "C:\Program Files\FreeCAD 1.0\bin\freecadcmd.exe" tests\run_tests.py
& "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" tests\run_tests.py
```

The runner uses `AutoBodyExportTests` as its FreeCAD parameter namespace and
exits nonzero on failure.

For UI changes, regenerate the real widget screenshots and inspect them:

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe" `
  tools\capture_docs_screenshots.py
```

Verify automatic addon startup and the primary widgets from an installed or
linked `Mod/AutoBodyExport` directory:

```powershell
$env:AUTOBODYEXPORT_REQUIRE_STARTUP_LOAD = "1"
$env:AUTOBODYEXPORT_GUI_RESULT = "C:\tmp\autobodyexport-gui-result.txt"
& "C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe" tests\verify_gui.py
Get-Content $env:AUTOBODYEXPORT_GUI_RESULT
```

Also verify that saving an opted-in document creates valid STEP/STL output.

## Pull requests

- Keep each pull request focused on one behavior.
- Describe user-visible changes and exact verification performed.
- Update `CHANGELOG.md` when the change is release-relevant.
- Update both READMEs when user-facing behavior changes.
- Do not commit `.FCStd`, STEP, STL, backup, cache, log, or private model files.
