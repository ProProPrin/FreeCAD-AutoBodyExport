"""Verify addon GUI initialization and primary widgets in FreeCAD."""

from __future__ import annotations

import importlib
import os
import sys
from pkgutil import extend_path

import FreeCADGui as Gui
from PySide import QtGui, QtWidgets

import freecad

REPOSITORY_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPOSITORY_ROOT)
freecad.__path__ = extend_path(freecad.__path__, freecad.__name__)
os.environ["AUTOBODYEXPORT_PARAMETER_PATH"] = (
    "User parameter:BaseApp/Preferences/Mod/AutoBodyExportGuiTests"
)

if (
    os.environ.get("AUTOBODYEXPORT_REQUIRE_STARTUP_LOAD") == "1"
    and "freecad.AutoBodyExport.init_gui" not in sys.modules
):
    raise RuntimeError("Addon was not loaded automatically from the FreeCAD Mod directory")

entry_point = importlib.import_module("InitGui")
from freecad.AutoBodyExport import core, preferences  # noqa: E402


def main() -> None:
    core.clear_document_states()
    core.save_export_options(
        core.ExportOptions(
            export_step=True,
            export_stl=True,
            show_dialog=True,
            enabled=True,
        )
    )

    icon_path = os.path.join(
        REPOSITORY_ROOT,
        "freecad",
        "AutoBodyExport",
        "Resources",
        "icons",
        "AutoBodyExport.svg",
    )
    if QtGui.QIcon(icon_path).isNull():
        raise RuntimeError("Addon SVG icon could not be loaded")

    page = preferences.PreferencesPage()
    page.loadSettings()
    if not page.enabled_checkbox.isChecked():
        raise RuntimeError("Preferences did not load the global enable setting")

    inventory = core.Inventory(
        parts=(core.PartInfo("Part", "Assembly", None),),
        bodies=(core.BodyInfo("Body", "Main Body", "part:Part"),),
    )
    selection = core.SelectionDialog(
        document_label="GUI Verification",
        inventory=inventory,
        selected_target_ids={"body:Body"},
        target_groups=(),
        new_item_ids={"body:Body"},
        options=core.load_export_options(),
        document_enabled=True,
    )
    if not selection.document_enabled_checkbox.isChecked():
        raise RuntimeError("Document opt-in control was not initialized")

    progress = core.ExportProgress(enabled=True)
    progress.start(2)
    if progress.dialog is None:
        raise RuntimeError("Progress dialog was not created")
    progress.advance("GUI verification")
    progress.close()

    selection.dialog.close()
    page.form.close()
    observer = getattr(entry_point._init_gui, "observer_singleton", None)
    if observer is not None:
        observer.stop()
    core.clear_document_states()
    result_path = os.environ.get("AUTOBODYEXPORT_GUI_RESULT")
    if result_path:
        with open(result_path, "w", encoding="utf-8") as result_file:
            result_file.write("GUI verification passed.\n")
    print("GUI verification passed.")
    QtWidgets.QApplication.processEvents()
    Gui.getMainWindow().close()


main()
