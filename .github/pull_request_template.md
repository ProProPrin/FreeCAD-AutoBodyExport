## Summary

Describe the behavior changed, why it is needed, and the affected workflow.

## Verification

List the exact commands, FreeCAD versions, and manual scenarios tested.

- [ ] `python tests/validate_release.py`
- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] FreeCAD 1.0 tests, or not applicable with an explanation
- [ ] FreeCAD 1.1 tests, or not applicable with an explanation
- [ ] Selection dialog and Preferences page checked when UI behavior changed

## Documentation

- [ ] `CHANGELOG.md` updated for a release-relevant change
- [ ] English and Japanese READMEs/user guides updated for user-facing behavior
- [ ] English and Japanese screenshots regenerated for documented UI changes

## Safety

- [ ] No `.FCStd`, STEP, STL, backup, cache, log, generated output, credential,
      or private path is included.
- [ ] Existing unmanaged export files remain protected.
- [ ] Managed-path validation and failure recovery remain covered.
