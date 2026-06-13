"""GUI initialization for Auto Body Export."""

import os

import FreeCADGui as Gui

from . import core
from .preferences import AutoBodyExportPreferencesPage


def initialize_gui():
    translation_directory = os.path.join(os.path.dirname(__file__), "Resources", "translations")
    if hasattr(Gui, "addLanguagePath"):
        Gui.addLanguagePath(translation_directory)
    if hasattr(Gui, "updateLocale"):
        Gui.updateLocale()
    if hasattr(Gui, "addPreferencePage"):
        Gui.addPreferencePage(AutoBodyExportPreferencesPage, "Auto Body Export")
    return core.initialize()


observer_singleton = initialize_gui()
