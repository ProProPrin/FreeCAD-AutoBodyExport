# Auto Body Export

Automatically export selected FreeCAD Bodies and independent Part objects to
STEP, STL, or both after every successful document save.

![Export selection dialog](https://raw.githubusercontent.com/ProProPrin/FreeCAD-AutoBodyExport/main/docs/images/selection-dialog.png)

## Highlights

- Per-document target selection with optional grouped output inside the same
  `App::Part`
- Explicit global and document-level enable controls
- Stable current filenames with bounded `old_versions/vN/` history
- Protection for files not created by the addon
- Global and per-document output directories, filename template, STL quality,
  and language settings
- Unchanged-geometry detection and optional progress display

![Auto Body Export preferences](https://raw.githubusercontent.com/ProProPrin/FreeCAD-AutoBodyExport/main/docs/images/preferences.png)

## Start exporting

1. Install the addon and restart FreeCAD.
2. Open **Edit > Preferences > Auto Body Export**.
3. Enable the addon globally and select STEP, STL, or both.
4. Save an `.FCStd` document and select its export targets.

Auto Body Export is disabled by default. Installation alone does not create
files, and existing files not managed by the addon are never overwritten.

[Full documentation](https://github.com/ProProPrin/FreeCAD-AutoBodyExport#readme)
| [日本語](https://github.com/ProProPrin/FreeCAD-AutoBodyExport/blob/main/README_ja.md)
