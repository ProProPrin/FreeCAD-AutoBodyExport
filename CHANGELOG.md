# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Reorganized the English and Japanese documentation around concise READMEs
  and complete user guides, with clearer setup, configuration, output safety,
  and troubleshooting information.
- Expanded contribution, security, issue, and pull request guidance so reports
  and changes include the context needed for reliable verification.

### Fixed

- Prevented the Auto Body Export preferences page from colliding with FreeCAD's
  Assembly preferences page.
- Restored the export selection dialog after saving when the global and
  per-save dialog options are enabled.
- Made addon-owned UI text follow FreeCAD's language setting: Japanese for
  Japanese and English for every other language.
- Added a preferences override for following FreeCAD, English, or Japanese.

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
