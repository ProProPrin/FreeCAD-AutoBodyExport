"""Small runtime translation layer for addon-owned widgets."""

import os

import FreeCAD as App
from PySide import QtCore

GENERAL_PREFERENCES_PATH = "User parameter:BaseApp/Preferences/General"
DEFAULT_ADDON_PARAMETER_PATH = "User parameter:BaseApp/Preferences/Mod/AutoBodyExport"
UI_LANGUAGE_KEY = "UILanguage"
UI_LANGUAGE_FREECAD = "freecad"
UI_LANGUAGE_ENGLISH = "en"
UI_LANGUAGE_JAPANESE = "ja"
UI_LANGUAGE_VALUES = {
    UI_LANGUAGE_FREECAD,
    UI_LANGUAGE_ENGLISH,
    UI_LANGUAGE_JAPANESE,
}

_JA = {
    "Interface language": "表示言語",
    "Follow FreeCAD": "FreeCADの設定に従う",
    "English": "英語",
    "Japanese": "日本語",
    "Language changes apply when a new addon dialog is opened.": (
        "言語の変更は、次にアドオンの画面を開いたときに反映されます。"
    ),
    "Enable Auto Body Export globally": "Auto Body Exportを全体で有効にする",
    "Enable automatic export for this document": "このドキュメントの自動出力を有効にする",
    (
        'Select the Bodies and independent objects to export from "{document}". '
        "Use the Group column to export multiple targets in the same Part as one file."
    ): (
        '"{document}" から出力するBodyと独立オブジェクトを選択してください。'
        "同じPart内の複数対象を1ファイルにまとめる場合はグループ列を使用します。"
    ),
    "File formats": "ファイル形式",
    "Selection dialog": "選択ダイアログ",
    "Show the export selection dialog every time the document is saved": (
        "ドキュメント保存時に毎回出力対象ダイアログを表示する"
    ),
    ("The dialog will still appear when a new Part, Body, or independent object is detected."): (
        "新しいPart、Body、独立オブジェクトを検出した場合はダイアログを表示します。"
    ),
    "Output": "出力",
    "Beside each document": "各ドキュメントと同じ場所",
    "Custom directory": "指定したディレクトリ",
    "Browse...": "参照...",
    "Filename template": "ファイル名テンプレート",
    "Available fields: {document}, {part}, {target}, {name}": (
        "利用可能: {document}, {part}, {target}, {name}"
    ),
    "History versions to keep": "保持する履歴世代数",
    "Use 0 to replace files without keeping history.": ("0の場合は履歴を保存せず置き換えます。"),
    "Skip exports when geometry and settings are unchanged": (
        "形状と設定が未変更の場合は出力を省略する"
    ),
    "Show progress while exporting": "出力中に進捗を表示する",
    "STL quality": "STL品質",
    "Linear deflection": "線形偏差",
    "Angular deflection (radians)": "角度偏差（ラジアン）",
    "Saved selections by CAD file": "CADファイルごとの保存済み設定",
    "CAD file": "CADファイル",
    "Enabled": "有効",
    "Selected targets": "選択対象数",
    "Managed files": "管理ファイル数",
    "Remove selected entries": "選択項目を削除",
    "Remove all entries": "すべて削除",
    "Remove the saved selections for all CAD files?": (
        "すべてのCADファイルの保存済み設定を削除しますか？"
    ),
    "Yes": "はい",
    "No": "いいえ",
    "Select at least one file format: STEP or STL.": ("STEPまたはSTLを1つ以上選択してください。"),
    "Select a custom output directory.": "出力先ディレクトリを指定してください。",
    "The filename template must contain at least one supported field.": (
        "ファイル名テンプレートには利用可能なフィールドを1つ以上含めてください。"
    ),
    "Auto Body Export": "Auto Body Export",
    "Select all": "すべて選択",
    "Clear all": "すべて解除",
    "Do not show this dialog next time": "次回からこのダイアログを表示しない",
    "Part / Export target": "Part / 出力対象",
    "Type": "種類",
    "Group": "グループ",
    "Status": "状態",
    "Part": "Part",
    "Body": "Body",
    "Object": "オブジェクト",
    "No Part": "Partなし",
    "No targets": "対象なし",
    "Group {number} - {count} items": "グループ {number} - {count}項目",
    "NEW": "新規",
    "Individual": "個別",
    "Export this target as an individual file.": ("この対象を個別ファイルとして出力します。"),
    "Export in the same file as this row": "この行と同じファイルへ出力",
    "Exporting selected targets...": "選択した対象を出力しています...",
    "Cancel": "キャンセル",
    "OK": "OK",
    "Some targets could not be exported:": "一部の対象を出力できませんでした:",
    "Post-save processing failed.": "保存後の出力処理に失敗しました。",
}


def _addon_preferences():
    parameter_path = os.environ.get("AUTOBODYEXPORT_PARAMETER_PATH", DEFAULT_ADDON_PARAMETER_PATH)
    return App.ParamGet(parameter_path)


def load_ui_language():
    language = _addon_preferences().GetString(UI_LANGUAGE_KEY, UI_LANGUAGE_FREECAD)
    return language if language in UI_LANGUAGE_VALUES else UI_LANGUAGE_FREECAD


def save_ui_language(language):
    if language not in UI_LANGUAGE_VALUES:
        language = UI_LANGUAGE_FREECAD
    _addon_preferences().SetString(UI_LANGUAGE_KEY, language)


def _language_code(configured_language, fallback_locale):
    """Return the addon language for a FreeCAD language setting."""
    language = configured_language.strip().lower().replace("_", "-")
    if language:
        return "ja" if language in {"ja", "japanese"} or language.startswith("ja-") else "en"
    locale = fallback_locale.strip().lower().replace("_", "-")
    return "ja" if locale == "ja" or locale.startswith("ja-") else "en"


def _configured_freecad_language():
    return App.ParamGet(GENERAL_PREFERENCES_PATH).GetString("Language", "")


def _current_locale_name():
    return QtCore.QLocale().name()


def current_language_code():
    """Return Japanese only when FreeCAD is using Japanese."""
    override = load_ui_language()
    if override != UI_LANGUAGE_FREECAD:
        return override
    return _language_code(_configured_freecad_language(), _current_locale_name())


def tr(text):
    """Translate addon-owned English source text for FreeCAD's UI language."""
    if current_language_code() == "ja":
        return _JA.get(text, text)
    return text
