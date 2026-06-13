"""Capture documentation screenshots from the real FreeCAD Qt widgets."""

from __future__ import annotations

import os
import sys
from pkgutil import extend_path

import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

import freecad

REPOSITORY_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUTPUT_DIRECTORY = os.path.join(REPOSITORY_ROOT, "docs", "images")
sys.path.insert(0, REPOSITORY_ROOT)
freecad.__path__ = extend_path(freecad.__path__, freecad.__name__)

from freecad.AutoBodyExport import core as export  # noqa: E402
from freecad.AutoBodyExport import preferences  # noqa: E402

QtCore.QLocale.setDefault(QtCore.QLocale("en_US"))


def save_widget(widget, filename: str) -> None:
    widget.show()
    widget.raise_()
    QtWidgets.QApplication.processEvents()
    image = widget.grab()
    if image.width() > 1024:
        image = image.scaledToWidth(1024, QtCore.Qt.SmoothTransformation)
    output_path = os.path.join(OUTPUT_DIRECTORY, filename)
    if not image.save(output_path, "PNG"):
        raise RuntimeError(f"Failed to save {output_path}")
    widget.close()


def capture_selection_dialog() -> None:
    inventory = export.Inventory(
        parts=(
            export.PartInfo("Frame", "Frame Assembly", None),
            export.PartInfo("Cover", "Cover", None),
        ),
        bodies=(
            export.BodyInfo("MainBody", "Main Body", "part:Frame"),
            export.BodyInfo("Bracket", "Mounting Bracket", "part:Frame"),
            export.BodyInfo("CoverBody", "Cover Body", "part:Cover"),
        ),
        objects=(
            export.ObjectInfo("Pin", "Alignment Pin", "Part::Feature", "part:Frame"),
            export.ObjectInfo("Plate", "Reference Plate", "Part::Feature", "part:Frame"),
        ),
    )
    dialog = export.SelectionDialog(
        document_label="Assembly Example",
        inventory=inventory,
        selected_target_ids={
            "body:MainBody",
            "body:Bracket",
            "object:Pin",
            "body:CoverBody",
        },
        target_groups=[
            {"body:MainBody", "body:Bracket", "object:Pin"},
        ],
        new_item_ids={"object:Plate"},
        options=export.ExportOptions(
            export_step=True,
            export_stl=True,
            show_dialog=True,
            enabled=True,
        ),
        document_enabled=True,
    )
    dialog.dialog.resize(1000, 650)
    save_widget(dialog.dialog, "selection-dialog.png")


def capture_preferences() -> None:
    original_list_document_states = export.list_document_states
    original_load_export_options = export.load_export_options
    export.list_document_states = lambda: [
        export.DocumentState(
            path=r"C:\Models\assembly.FCStd",
            known_item_ids={
                "part:Frame",
                "body:MainBody",
                "body:Bracket",
                "object:Pin",
            },
            selected_target_ids={
                "body:MainBody",
                "body:Bracket",
                "object:Pin",
            },
            target_groups=[
                {"body:MainBody", "body:Bracket", "object:Pin"},
            ],
            enabled=True,
            generated_files={
                r"C:\Models\step\assembly_Frame_Main Body.step",
                r"C:\Models\stl\assembly_Frame_Main Body.stl",
            },
            managed_output_roots={r"C:\Models"},
        )
    ]
    export.load_export_options = lambda: export.ExportOptions(
        export_step=True,
        export_stl=True,
        show_dialog=True,
        enabled=True,
        history_limit=20,
        stl_linear_deflection=0.1,
        stl_angular_deflection=0.5,
        show_progress=True,
        skip_unchanged=True,
    )
    try:
        page = preferences.PreferencesPage()
        page.form.setWindowTitle("Auto Body Export Preferences")
        page.form.resize(900, 820)
        page.loadSettings()
        save_widget(page.form, "preferences.png")
    finally:
        export.list_document_states = original_list_document_states
        export.load_export_options = original_load_export_options


def main() -> None:
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    capture_selection_dialog()
    capture_preferences()
    print(f"Saved documentation screenshots to {OUTPUT_DIRECTORY}")
    QtCore.QTimer.singleShot(0, QtWidgets.QApplication.instance().quit)
    Gui.getMainWindow().close()


main()
