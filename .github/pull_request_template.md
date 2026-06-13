## Summary

Describe the behavior changed and why.

## Verification

- [ ] `python tests/validate_release.py`
- [ ] FreeCAD 1.0 tests
- [ ] FreeCAD 1.1 tests
- [ ] Selection dialog and Preferences page checked when UI changed

## Safety

- [ ] No `.FCStd`, STEP, STL, backup, generated output, or private path is included.
- [ ] Existing unmanaged export files remain protected.
