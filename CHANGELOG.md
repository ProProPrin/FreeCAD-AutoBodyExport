# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-06-13

### Added

- Automatic STEP and STL export after saving a FreeCAD document.
- Per-document target selection and grouping inside the same `App::Part`.
- Global and per-document opt-in controls.
- Configurable output directory, filename template, history retention, STL
  mesh precision, progress display, and unchanged-geometry skipping.
- Collision-safe filenames and protection for files not created by the addon.
- Bounded history and retirement of obsolete managed exports.
- English and Japanese UI text and documentation.
- FreeCAD 1.0 and 1.1 test coverage and GitHub Actions validation.

[Unreleased]: https://github.com/ProProPrin/FreeCAD-AutoBodyExport/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ProProPrin/FreeCAD-AutoBodyExport/releases/tag/v1.0.0
