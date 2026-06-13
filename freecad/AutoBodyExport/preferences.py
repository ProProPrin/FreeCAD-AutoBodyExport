"""FreeCAD Preferences page for Auto Body Export."""

import os

import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from . import core, i18n
from .i18n import tr


class AutoBodyExportPreferencesPage:
    def __init__(self, parent=None):
        ui_path = os.path.join(
            os.path.dirname(__file__),
            "Resources",
            "ui",
            "AutoBodyExportPreferences.ui",
        )
        self.form = Gui.PySideUic.loadUi(ui_path)
        self._states_by_path = {}
        self._build_ui()

    def _build_ui(self):
        layout = self.form.layout()

        language_group = QtWidgets.QGroupBox(tr("Interface language"))
        language_layout = QtWidgets.QVBoxLayout(language_group)
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.setObjectName("AutoBodyExportLanguage")
        self.language_combo.addItem(tr("Follow FreeCAD"), i18n.UI_LANGUAGE_FREECAD)
        self.language_combo.addItem(tr("English"), i18n.UI_LANGUAGE_ENGLISH)
        self.language_combo.addItem(tr("Japanese"), i18n.UI_LANGUAGE_JAPANESE)
        language_layout.addWidget(self.language_combo)
        language_note = QtWidgets.QLabel(
            tr("Language changes apply when a new addon dialog is opened.")
        )
        language_note.setWordWrap(True)
        language_layout.addWidget(language_note)
        layout.addWidget(language_group)

        self.enabled_checkbox = QtWidgets.QCheckBox(tr("Enable Auto Body Export globally"))
        self.enabled_checkbox.setObjectName("AutoBodyExportEnabled")
        enabled_font = self.enabled_checkbox.font()
        enabled_font.setBold(True)
        self.enabled_checkbox.setFont(enabled_font)
        layout.addWidget(self.enabled_checkbox)

        format_group = QtWidgets.QGroupBox(tr("File formats"))
        format_layout = QtWidgets.QHBoxLayout(format_group)
        self.step_checkbox = QtWidgets.QCheckBox("STEP")
        self.stl_checkbox = QtWidgets.QCheckBox("STL")
        format_layout.addWidget(self.step_checkbox)
        format_layout.addWidget(self.stl_checkbox)
        format_layout.addStretch()
        layout.addWidget(format_group)

        output_group = QtWidgets.QGroupBox(tr("Output"))
        output_layout = QtWidgets.QGridLayout(output_group)
        self.output_mode_combo = QtWidgets.QComboBox()
        self.output_mode_combo.addItem(tr("Beside each document"), core.OUTPUT_MODE_DOCUMENT)
        self.output_mode_combo.addItem(tr("Custom directory"), core.OUTPUT_MODE_CUSTOM)
        self.output_mode_combo.currentIndexChanged.connect(self._update_output_controls)
        output_layout.addWidget(self.output_mode_combo, 0, 0, 1, 3)

        self.custom_output_edit = QtWidgets.QLineEdit()
        self.custom_output_button = QtWidgets.QPushButton(tr("Browse..."))
        self.custom_output_button.clicked.connect(self._browse_output_directory)
        output_layout.addWidget(self.custom_output_edit, 1, 0, 1, 2)
        output_layout.addWidget(self.custom_output_button, 1, 2)

        output_layout.addWidget(QtWidgets.QLabel(tr("Filename template")), 2, 0)
        self.filename_template_edit = QtWidgets.QLineEdit()
        output_layout.addWidget(self.filename_template_edit, 2, 1, 1, 2)
        template_note = QtWidgets.QLabel(
            tr("Available fields: {document}, {part}, {target}, {name}")
        )
        template_note.setWordWrap(True)
        output_layout.addWidget(template_note, 3, 0, 1, 3)

        output_layout.addWidget(QtWidgets.QLabel(tr("History versions to keep")), 4, 0)
        self.history_limit_spin = QtWidgets.QSpinBox()
        self.history_limit_spin.setRange(0, 1000)
        output_layout.addWidget(self.history_limit_spin, 4, 1)
        history_note = QtWidgets.QLabel(tr("Use 0 to replace files without keeping history."))
        history_note.setWordWrap(True)
        output_layout.addWidget(history_note, 5, 0, 1, 3)

        self.skip_unchanged_checkbox = QtWidgets.QCheckBox(
            tr("Skip exports when geometry and settings are unchanged")
        )
        output_layout.addWidget(self.skip_unchanged_checkbox, 6, 0, 1, 3)
        self.show_progress_checkbox = QtWidgets.QCheckBox(tr("Show progress while exporting"))
        output_layout.addWidget(self.show_progress_checkbox, 7, 0, 1, 3)
        layout.addWidget(output_group)

        stl_group = QtWidgets.QGroupBox(tr("STL quality"))
        stl_layout = QtWidgets.QFormLayout(stl_group)
        self.linear_deflection_spin = QtWidgets.QDoubleSpinBox()
        self.linear_deflection_spin.setDecimals(4)
        self.linear_deflection_spin.setRange(0.001, 1000.0)
        self.linear_deflection_spin.setSingleStep(0.05)
        self.angular_deflection_spin = QtWidgets.QDoubleSpinBox()
        self.angular_deflection_spin.setDecimals(4)
        self.angular_deflection_spin.setRange(0.01, 3.1416)
        self.angular_deflection_spin.setSingleStep(0.05)
        stl_layout.addRow(tr("Linear deflection"), self.linear_deflection_spin)
        stl_layout.addRow(
            tr("Angular deflection (radians)"),
            self.angular_deflection_spin,
        )
        layout.addWidget(stl_group)

        display_group = QtWidgets.QGroupBox(tr("Selection dialog"))
        display_layout = QtWidgets.QVBoxLayout(display_group)
        self.show_dialog_checkbox = QtWidgets.QCheckBox(
            tr("Show the export selection dialog every time the document is saved")
        )
        self.show_dialog_checkbox.setObjectName("AutoBodyExportShowDialog")
        display_layout.addWidget(self.show_dialog_checkbox)
        display_note = QtWidgets.QLabel(
            tr(
                "The dialog will still appear when a new Part, Body, or "
                "independent object is detected."
            )
        )
        display_note.setWordWrap(True)
        display_layout.addWidget(display_note)
        layout.addWidget(display_group)

        states_group = QtWidgets.QGroupBox(tr("Saved selections by CAD file"))
        states_layout = QtWidgets.QVBoxLayout(states_group)
        self.states_tree = QtWidgets.QTreeWidget()
        self.states_tree.setColumnCount(4)
        self.states_tree.setHeaderLabels(
            [
                tr("CAD file"),
                tr("Enabled"),
                tr("Selected targets"),
                tr("Managed files"),
            ]
        )
        self.states_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        states_layout.addWidget(self.states_tree)

        button_layout = QtWidgets.QHBoxLayout()
        self.remove_selected_button = QtWidgets.QPushButton(tr("Remove selected entries"))
        self.remove_selected_button.clicked.connect(self._remove_selected_states)
        self.remove_all_button = QtWidgets.QPushButton(tr("Remove all entries"))
        self.remove_all_button.clicked.connect(self._remove_all_states)
        button_layout.addWidget(self.remove_selected_button)
        button_layout.addWidget(self.remove_all_button)
        button_layout.addStretch()
        states_layout.addLayout(button_layout)
        layout.addWidget(states_group, 1)

    def loadSettings(self):
        options = core.load_export_options()
        language_index = self.language_combo.findData(i18n.load_ui_language())
        self.language_combo.setCurrentIndex(max(0, language_index))
        self.enabled_checkbox.setChecked(options.enabled)
        self.step_checkbox.setChecked(options.export_step)
        self.stl_checkbox.setChecked(options.export_stl)
        self.show_dialog_checkbox.setChecked(options.show_dialog)
        self.custom_output_edit.setText(options.custom_output_directory)
        self.filename_template_edit.setText(options.filename_template)
        self.history_limit_spin.setValue(options.history_limit)
        self.linear_deflection_spin.setValue(options.stl_linear_deflection)
        self.angular_deflection_spin.setValue(options.stl_angular_deflection)
        self.show_progress_checkbox.setChecked(options.show_progress)
        self.skip_unchanged_checkbox.setChecked(options.skip_unchanged)
        index = self.output_mode_combo.findData(options.output_mode)
        self.output_mode_combo.setCurrentIndex(max(0, index))
        self._update_output_controls()
        self._reload_states()

    def saveSettings(self):
        i18n.save_ui_language(self.language_combo.currentData())
        if not self.step_checkbox.isChecked() and not self.stl_checkbox.isChecked():
            self.step_checkbox.setChecked(True)
        output_mode = self.output_mode_combo.currentData()
        custom_directory = self.custom_output_edit.text().strip()
        if output_mode == core.OUTPUT_MODE_CUSTOM and not custom_directory:
            output_mode = core.OUTPUT_MODE_DOCUMENT
            self.output_mode_combo.setCurrentIndex(
                self.output_mode_combo.findData(core.OUTPUT_MODE_DOCUMENT)
            )
        filename_template = self.filename_template_edit.text().strip()
        if not core.validate_filename_template(filename_template):
            filename_template = core.DEFAULT_FILENAME_TEMPLATE
            self.filename_template_edit.setText(filename_template)

        core.save_export_options(
            core.ExportOptions(
                export_step=self.step_checkbox.isChecked(),
                export_stl=self.stl_checkbox.isChecked(),
                show_dialog=self.show_dialog_checkbox.isChecked(),
                enabled=self.enabled_checkbox.isChecked(),
                output_mode=output_mode,
                custom_output_directory=custom_directory,
                filename_template=filename_template,
                history_limit=self.history_limit_spin.value(),
                stl_linear_deflection=self.linear_deflection_spin.value(),
                stl_angular_deflection=self.angular_deflection_spin.value(),
                show_progress=self.show_progress_checkbox.isChecked(),
                skip_unchanged=self.skip_unchanged_checkbox.isChecked(),
            )
        )
        changed_states = []
        for index in range(self.states_tree.topLevelItemCount()):
            item = self.states_tree.topLevelItem(index)
            path = item.data(0, QtCore.Qt.UserRole)
            state = self._states_by_path.get(path)
            if state is None:
                continue
            state.enabled = item.checkState(1) == QtCore.Qt.Checked
            changed_states.append(state)
        core.save_document_states(changed_states)

    def _update_output_controls(self):
        is_custom = self.output_mode_combo.currentData() == core.OUTPUT_MODE_CUSTOM
        self.custom_output_edit.setEnabled(is_custom)
        self.custom_output_button.setEnabled(is_custom)

    def _browse_output_directory(self):
        start_directory = self.custom_output_edit.text().strip()
        if not start_directory:
            start_directory = os.path.expanduser("~")
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self.form, tr("Custom directory"), start_directory
        )
        if directory:
            self.custom_output_edit.setText(directory)

    def _reload_states(self):
        self.states_tree.clear()
        self._states_by_path = {state.path: state for state in core.list_document_states()}
        for state in self._states_by_path.values():
            item = QtWidgets.QTreeWidgetItem(self.states_tree)
            item.setText(0, os.path.basename(state.path) or state.path)
            item.setToolTip(0, state.path)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(1, QtCore.Qt.Checked if state.enabled else QtCore.Qt.Unchecked)
            item.setText(2, str(len(state.selected_target_ids)))
            item.setText(3, str(len(state.generated_files)))
            item.setData(0, QtCore.Qt.UserRole, state.path)
        for column in range(4):
            self.states_tree.resizeColumnToContents(column)

    def _remove_selected_states(self):
        paths = [item.data(0, QtCore.Qt.UserRole) for item in self.states_tree.selectedItems()]
        if not paths:
            return
        core.remove_document_states(paths)
        self._reload_states()

    def _remove_all_states(self):
        if self.states_tree.topLevelItemCount() == 0:
            return
        message_box = QtWidgets.QMessageBox(self.form)
        message_box.setWindowTitle(tr("Auto Body Export"))
        message_box.setText(tr("Remove the saved selections for all CAD files?"))
        message_box.setIcon(QtWidgets.QMessageBox.Question)
        message_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        message_box.setDefaultButton(QtWidgets.QMessageBox.No)
        message_box.button(QtWidgets.QMessageBox.Yes).setText(tr("Yes"))
        message_box.button(QtWidgets.QMessageBox.No).setText(tr("No"))
        if hasattr(message_box, "exec"):
            answer = message_box.exec()
        else:
            answer = message_box.exec_()
        if answer != QtWidgets.QMessageBox.Yes:
            return
        core.clear_document_states()
        self._reload_states()
