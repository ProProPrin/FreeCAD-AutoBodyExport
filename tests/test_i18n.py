import unittest
from unittest import mock

from freecad.AutoBodyExport import i18n


class AutoBodyExportI18nTests(unittest.TestCase):
    def test_explicit_japanese_uses_japanese(self):
        self.assertEqual(i18n._language_code("Japanese", "en_US"), "ja")
        self.assertEqual(i18n._language_code("ja", "en_US"), "ja")
        self.assertEqual(i18n._language_code("ja-JP", "en_US"), "ja")

    def test_explicit_non_japanese_uses_english(self):
        self.assertEqual(i18n._language_code("English", "ja_JP"), "en")
        self.assertEqual(i18n._language_code("German", "ja_JP"), "en")

    def test_automatic_language_uses_japanese_only_for_japanese_locale(self):
        self.assertEqual(i18n._language_code("", "ja_JP"), "ja")
        self.assertEqual(i18n._language_code("", "en_US"), "en")
        self.assertEqual(i18n._language_code("", "de_DE"), "en")

    def test_translation_uses_freecad_language_setting(self):
        with (
            mock.patch.object(i18n, "load_ui_language", return_value=i18n.UI_LANGUAGE_FREECAD),
            mock.patch.object(i18n, "_configured_freecad_language", return_value="English"),
            mock.patch.object(i18n, "_current_locale_name", return_value="ja_JP"),
        ):
            self.assertEqual(i18n.tr("File formats"), "File formats")

        with (
            mock.patch.object(i18n, "load_ui_language", return_value=i18n.UI_LANGUAGE_FREECAD),
            mock.patch.object(i18n, "_configured_freecad_language", return_value="Japanese"),
            mock.patch.object(i18n, "_current_locale_name", return_value="en_US"),
        ):
            self.assertEqual(i18n.tr("File formats"), "ファイル形式")

    def test_explicit_addon_language_overrides_freecad(self):
        with mock.patch.object(i18n, "load_ui_language", return_value=i18n.UI_LANGUAGE_ENGLISH):
            self.assertEqual(i18n.current_language_code(), "en")
        with mock.patch.object(i18n, "load_ui_language", return_value=i18n.UI_LANGUAGE_JAPANESE):
            self.assertEqual(i18n.current_language_code(), "ja")

    def test_addon_language_setting_round_trip(self):
        preferences = i18n._addon_preferences()
        original = preferences.GetString(i18n.UI_LANGUAGE_KEY, "")
        try:
            i18n.save_ui_language(i18n.UI_LANGUAGE_JAPANESE)
            self.assertEqual(i18n.load_ui_language(), i18n.UI_LANGUAGE_JAPANESE)
            i18n.save_ui_language("unsupported")
            self.assertEqual(i18n.load_ui_language(), i18n.UI_LANGUAGE_FREECAD)
        finally:
            if original:
                preferences.SetString(i18n.UI_LANGUAGE_KEY, original)
            else:
                preferences.RemString(i18n.UI_LANGUAGE_KEY)


if __name__ == "__main__":
    unittest.main()
