# Contributing

Contributions and reproducible bug reports are welcome. Keep changes focused,
preserve the addon's file-safety guarantees, and include verification that
matches the affected behavior.

## Getting started

1. Clone the repository.
2. Install or link it as FreeCAD's user `Mod/AutoBodyExport` directory.
3. Restart FreeCAD after changing addon initialization or GUI registration.
4. Confirm that **Edit > Preferences > Auto Body Export** is available.

FreeCAD's user application directory is available from its Python console:

```python
FreeCAD.getUserAppDataDir()
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `freecad/AutoBodyExport/` | Runtime, preferences, and localization code |
| `Init.py`, `InitGui.py` | Compatibility entry points loaded by FreeCAD |
| `tests/` | Core, localization, GUI, and release validation |
| `tools/capture_docs_screenshots.py` | Documentation screenshot capture |
| `docs/` | User guides and documentation images |
| `package.xml` | FreeCAD Addon Manager metadata |

Match the existing code style and add focused tests for behavior changes. Do
not weaken:

- global and document-level opt-in;
- protection for unmanaged files;
- managed-path validation;
- temporary-file replacement and rollback;
- delayed retirement of obsolete managed exports.

## Reporting issues

Use the appropriate GitHub issue form and provide:

- FreeCAD, Auto Body Export, and operating-system versions;
- output format and output mode;
- a minimal description of the relevant Part/Body/object structure;
- exact reproduction steps and expected behavior;
- actual behavior and FreeCAD Report view output.

Remove private paths, credentials, and confidential model data. Do not attach
production CAD files; create a minimal replacement model instead. Report
suspected vulnerabilities privately according to [SECURITY.md](SECURITY.md).

## Validation

### Release and style checks

```powershell
python tests\validate_release.py
ruff check .
ruff format --check .
```

### FreeCAD core tests

Run the suite with both supported FreeCAD lines:

```powershell
$env:AUTOBODYEXPORT_TEST_TMP = "C:\tmp\autobodyexport-tests"
& "C:\Program Files\FreeCAD 1.0\bin\freecadcmd.exe" tests\run_tests.py
& "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" tests\run_tests.py
```

The runner uses the isolated `AutoBodyExportTests` parameter namespace and
exits nonzero on failure.

### GUI changes

Regenerate and inspect the real English and Japanese widgets:

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe" `
  tools\capture_docs_screenshots.py
```

Verify automatic startup and the primary widgets from an installed or linked
`Mod/AutoBodyExport` directory:

```powershell
$env:AUTOBODYEXPORT_REQUIRE_STARTUP_LOAD = "1"
$env:AUTOBODYEXPORT_GUI_RESULT = "C:\tmp\autobodyexport-gui-result.txt"
& "C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe" tests\verify_gui.py
Get-Content $env:AUTOBODYEXPORT_GUI_RESULT
```

Also save an opted-in document and confirm that valid STEP/STL output is
created. UI changes must keep the English and Japanese screenshots current.

## Pull requests

- Explain the user-visible behavior and why it changed.
- List the exact commands and FreeCAD versions used for verification.
- Add or update tests for behavior changes.
- Update `CHANGELOG.md` for release-relevant changes.
- Update both READMEs and both user guides when user-facing behavior changes.
- Include regenerated screenshots when documented UI changes.
- Do not commit `.FCStd`, STEP, STL, backup, cache, log, generated output, or
  private path data.
