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
repository_freecad_path = os.path.join(REPOSITORY_ROOT, "freecad")
freecad.__path__ = [
    repository_freecad_path,
    *[
        path
        for path in extend_path(freecad.__path__, freecad.__name__)
        if os.path.normcase(os.path.abspath(path))
        != os.path.normcase(os.path.abspath(repository_freecad_path))
    ],
]
os.environ["AUTOBODYEXPORT_PARAMETER_PATH"] = (
    "User parameter:BaseApp/Preferences/Mod/AutoBodyExportGuiTests"
)

if (
    os.environ.get("AUTOBODYEXPORT_REQUIRE_STARTUP_LOAD") == "1"
    and "freecad.AutoBodyExport.init_gui" not in sys.modules
):
    raise RuntimeError("Addon was not loaded automatically from the FreeCAD Mod directory")

entry_point = importlib.import_module("InitGui")
from freecad.AutoBodyExport import core, i18n, preferences  # noqa: E402


def _group_titles(widget):
    return {group.title() for group in widget.findChildren(QtWidgets.QGroupBox)}


def _verify_language_mode(language, expected_language):
    i18n.save_ui_language(language)
    page = preferences.AutoBodyExportPreferencesPage()
    page.loadSettings()

    if page.language_combo.currentData() != language:
        raise RuntimeError(f"Preferences did not load language mode {language!r}")

    if expected_language == i18n.UI_LANGUAGE_JAPANESE:
        expected_interface_title = "表示言語"
        expected_follow_freecad = "FreeCADの設定に従う"
        expected_enabled_text = "Auto Body Exportを全体で有効にする"
        expected_document_enabled_text = "このドキュメントの自動出力を有効にする"
        expected_clear_all = "すべて解除"
    else:
        expected_interface_title = "Interface language"
        expected_follow_freecad = "Follow FreeCAD"
        expected_enabled_text = "Enable Auto Body Export globally"
        expected_document_enabled_text = "Enable automatic export for this document"
        expected_clear_all = "Clear all"

    if expected_interface_title not in _group_titles(page.form):
        raise RuntimeError(f"Preferences did not use {expected_language} group labels")
    if page.language_combo.itemText(0) != expected_follow_freecad:
        raise RuntimeError(f"Language selector did not use {expected_language} labels")
    if page.enabled_checkbox.text() != expected_enabled_text:
        raise RuntimeError(f"Preferences did not use {expected_language} checkbox labels")

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
    if selection.document_enabled_checkbox.text() != expected_document_enabled_text:
        raise RuntimeError(f"Selection dialog did not use {expected_language} labels")
    button_texts = {
        button.text() for button in selection.dialog.findChildren(QtWidgets.QPushButton)
    }
    if expected_clear_all not in button_texts:
        raise RuntimeError(f"Selection dialog buttons did not use {expected_language} labels")

    selection.dialog.close()
    page.form.close()


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

    _verify_language_mode(i18n.UI_LANGUAGE_ENGLISH, i18n.UI_LANGUAGE_ENGLISH)
    _verify_language_mode(i18n.UI_LANGUAGE_JAPANESE, i18n.UI_LANGUAGE_JAPANESE)
    i18n.save_ui_language(i18n.UI_LANGUAGE_FREECAD)
    _verify_language_mode(i18n.UI_LANGUAGE_FREECAD, i18n.current_language_code())

    page = preferences.AutoBodyExportPreferencesPage()
    if (
        not isinstance(page.form, QtWidgets.QWidget)
        or page.form.objectName() != "AutoBodyExportPreferences"
        or page.form.layout() is None
    ):
        raise RuntimeError("Preferences UI was not loaded as an embeddable QWidget")
    page.loadSettings()
    if page.language_combo.count() != 3:
        raise RuntimeError("Preferences language selector was not initialized")
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
