# Auto Body Export

[日本語](README_ja.md)

Auto Body Export is a FreeCAD extension that exports selected
`PartDesign::Body` objects and independent shape objects inside `App::Part`
containers after a document is saved.

![Export selection dialog](https://raw.githubusercontent.com/ProProPrin/FreeCAD-AutoBodyExport/main/docs/images/selection-dialog.png)

The screenshots in this README are captured directly from the actual FreeCAD
1.1 Qt interface. They are not AI-generated images.

## Features

- Export STEP, STL, or both after a successful document save.
- Explicit global and per-document opt-in. Installation alone writes nothing.
- Remember targets and groups separately for each `.FCStd` file.
- Export multiple targets in the same `App::Part` as one file.
- Validate every group member before writing the group file.
- Avoid filename collisions and never overwrite files not managed by the addon.
- Archive replaced and obsolete managed files with a configurable history limit.
- Skip export when geometry and format settings are unchanged.
- Configure output location, filename template, STL mesh precision, progress,
  and selection-dialog behavior.
- English and Japanese addon UI text.

## Requirements

- FreeCAD 1.0 or later
- Python 3.11 or later, as bundled with supported FreeCAD releases
- A document saved to an `.FCStd` path

The automated suite covers FreeCAD 1.0 and 1.1. Windows is verified locally;
the CI workflow runs the same core tests with official Windows builds.

## Installation

### Manual installation

1. In the FreeCAD Python console, run:

   ```python
   FreeCAD.getUserAppDataDir()
   ```

2. Close FreeCAD.
3. Clone or extract this repository into the `Mod` directory below that path.
   Use `AutoBodyExport` as the destination directory name.
4. Restart FreeCAD.

Example for a typical Windows installation:

```powershell
git clone https://github.com/ProProPrin/FreeCAD-AutoBodyExport.git `
  "$env:APPDATA\FreeCAD\Mod\AutoBodyExport"
```

The installed directory must contain `Init.py`, `InitGui.py`, and
`package.xml` at its top level.

## Quick start

1. Open **Edit > Preferences > Auto Body Export**.
2. Enable **Auto Body Export globally** and choose at least one format.
3. Open or create a document and save it as `.FCStd`.
4. In the selection dialog, leave automatic export enabled for the document.
5. Select the Bodies and independent Part objects to export.
6. Use the **Group** column to combine targets from the same `App::Part`.
7. Select **OK**.

The extension is disabled by default. A document must be opted in through the
GUI before automatic export starts. Canceling the dialog skips only that save.

## Export targets and groups

The extension recognizes:

- `PartDesign::Body` objects, including Bodies outside an `App::Part`;
- shape-bearing objects directly inside an `App::Part`, excluding features
  already contained by a Body.

Targets can only be grouped with targets that have the same direct parent Part.
A group is exported only when every member still exists and has a non-empty
Shape. Object-only groups use a stable hash suffix so multiple groups cannot
collide.

## Output behavior

With the default output mode, `assembly.FCStd` produces:

```text
assembly.FCStd
step/
  assembly_Frame_Main Body.step
  old_versions/
    v0/
      assembly_Frame_Main Body_v0.step
stl/
  assembly_Frame_Main Body.stl
```

The current file keeps its normal name. On replacement, the previous managed
file moves to the next `old_versions/vN/` directory. History is pruned to the
configured number of versions; a limit of `0` replaces files without history.

When a target is deselected, renamed, deleted, regrouped, or a format is
disabled, its obsolete managed file is retired only after the complete export
run succeeds. Existing files that the extension did not create are preserved;
the new export receives a stable hash suffix instead.

For a custom output directory, each document receives a directory such as
`assembly_a1b2c3d4/`. The hash is derived from the source document directory,
so same-named documents from different projects do not overwrite each other.

## Filename template

The default template is:

```text
{document}_{part}_{target}
```

Available fields:

| Field | Value |
| --- | --- |
| `{document}` | `.FCStd` filename without its extension |
| `{part}` | Direct parent Part label, when present |
| `{target}` | Body label or grouped Body labels |
| `{name}` | Internal FreeCAD object name |

Invalid filesystem characters and Windows reserved names are sanitized. Long
names are truncated with a stable hash. Duplicate rendered names also receive
a hash suffix.

## Preferences

Open **Edit > Preferences > Auto Body Export** to configure:

- interface language: follow FreeCAD, English, or Japanese;
- global enable/disable;
- STEP and STL output;
- output beside each document or under a custom directory;
- filename template and history limit;
- unchanged-geometry skipping and progress display;
- STL linear and angular deflection;
- whether to show the selection dialog on every save;
- enable state and saved target counts for known CAD files.

![Auto Body Export preferences](https://raw.githubusercontent.com/ProProPrin/FreeCAD-AutoBodyExport/main/docs/images/preferences.png)

When the normal dialog is disabled, it still opens if a new Part, Body, or
independent object is detected. A document disabled in its first dialog can be
enabled later from the saved-document list in Preferences.

## Safety model

- Global and document-level opt-in are both required.
- Only files recorded as generated by this extension are archived or removed.
- Managed paths must be direct STEP/STL outputs under a recorded output root.
- All output uses a temporary file followed by replacement.
- If exporting or retiring a file fails, existing managed files remain tracked.
- Tests use a dedicated FreeCAD parameter namespace and never clear real user
  settings.

Keep backups of important CAD data. This extension automates file writes and
does not replace a project backup strategy.

## Testing

Validate release metadata and Python syntax:

```powershell
python tests\validate_release.py
```

Run the FreeCAD suite:

```powershell
$env:AUTOBODYEXPORT_TEST_TMP = "C:\tmp\autobodyexport-tests"
& "C:\Program Files\FreeCAD 1.0\bin\freecadcmd.exe" tests\run_tests.py
& "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" tests\run_tests.py
```

The test runner exits nonzero on failure. GitHub Actions repeats release
validation, Ruff checks, and the core suite with official FreeCAD 1.0.2 and
1.1.1 builds.

## Troubleshooting

- **No export is produced:** enable the extension globally, opt in the
  document, save to `.FCStd`, and select at least one format and target.
- **The Preferences page is missing:** confirm the addon directory is inside
  the `Mod` directory returned by `FreeCAD.getUserAppDataDir()` and restart
  FreeCAD.
- **A target is missing:** independent objects must have a Shape and be
  directly inside an `App::Part`; Body features are exported with their Body.
- **The filename has a hash:** the original name collided, was too long, or an
  unmanaged file already occupied the requested path.
- **A group is skipped:** inspect FreeCAD's Report view. One or more group
  members may be missing or have an empty Shape.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and test instructions.
Report suspected vulnerabilities privately as described in
[SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
