"""Compatibility entry point loaded automatically by FreeCAD."""

import importlib
from pkgutil import extend_path

import freecad

freecad.__path__ = extend_path(freecad.__path__, freecad.__name__)
_init_gui = importlib.import_module("freecad.AutoBodyExport.init_gui")
