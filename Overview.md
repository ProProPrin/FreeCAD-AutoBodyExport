# Auto Body Export

Automatically export selected FreeCAD Bodies and independent Part objects to
STEP, STL, or both whenever a document is saved.

![Export selection dialog](https://raw.githubusercontent.com/ProProPrin/FreeCAD-AutoBodyExport/main/docs/images/selection-dialog.png)

## Highlights

- Explicit global and per-document opt-in. Installation alone never starts
  writing export files.
- Per-document target selection with grouped export for targets in the same
  `App::Part`.
- Collision-safe filenames, unmanaged-file protection, and bounded history.
- Optional custom output directory and filename template.
- Configurable STL mesh precision, progress display, and unchanged-geometry
  skipping.
- English and Japanese UI text.

![Preferences](https://raw.githubusercontent.com/ProProPrin/FreeCAD-AutoBodyExport/main/docs/images/preferences.png)

## Quick start

1. Open **Edit > Preferences > Auto Body Export**.
2. Enable **Auto Body Export globally** and choose the output settings.
3. Save an `.FCStd` document.
4. Enable automatic export for that document and select the targets.

By default, the addon writes current files to `step/` and `stl/` beside the
document. Replaced and obsolete managed files are moved under
`old_versions/vN/`. Files that were not created by the addon are never
overwritten.

See the [full documentation](https://github.com/ProProPrin/FreeCAD-AutoBodyExport#readme)
for installation, settings, output rules, testing, and troubleshooting.
