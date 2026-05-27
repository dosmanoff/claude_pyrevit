#! python3
# -*- coding: utf-8 -*-
"""Settings dialog for the Claude assistant.

Edits %APPDATA%\\claude_pyrevit\\config.json. The file lives outside
this repository — no key ever lands in source control.

Also lets the user test that the key reaches Anthropic before saving.
"""

import os
import threading
import traceback

import clr  # noqa: F401
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

from System.Windows.Media import SolidColorBrush
from System.Windows.Media import Color as WpfColor

from pyrevit import forms  # noqa: F401

from claude_revit import config, user_config
from claude_revit.api_client import test_api_key


XAML_PATH = os.path.join(os.path.dirname(__file__), "SettingsWindow.xaml")

OK_BRUSH = SolidColorBrush(WpfColor.FromRgb(30, 130, 60))
ERR_BRUSH = SolidColorBrush(WpfColor.FromRgb(180, 50, 50))
INFO_BRUSH = SolidColorBrush(WpfColor.FromRgb(100, 100, 100))


class SettingsWindow(forms.WPFWindow):

    def __init__(self, xaml_path):
        forms.WPFWindow.__init__(self, xaml_path)

        # Pre-fill from existing config
        existing_key = user_config.api_key() or ""
        self.ApiKeyBox.Password = existing_key

        current_model = config.get_model()
        self._select_model(current_model)

        self.ConfigPathText.Text = "Config file: " + user_config.config_path()

        source = config.api_key_source()
        if source == "user_config":
            self.KeySourceText.Text = "Loaded from user config."
        elif source == "env":
            self.KeySourceText.Text = (
                "ANTHROPIC_API_KEY env var is currently in effect. "
                "Saving here will take precedence."
            )
        elif source == "local_config":
            self.KeySourceText.Text = (
                "_local_config.py is in effect (dev override)."
            )
        else:
            self.KeySourceText.Text = "No API key set yet."

        self.SaveButton.Click += self._on_save
        self.CancelButton.Click += self._on_cancel
        self.TestButton.Click += self._on_test

    def _select_model(self, model_name):
        if not model_name:
            self.ModelCombo.SelectedIndex = 0
            return
        for i in range(self.ModelCombo.Items.Count):
            item = self.ModelCombo.Items[i]
            if str(item.Content) == model_name:
                self.ModelCombo.SelectedIndex = i
                return
        # Unknown model — leave default selected; user can pick from list.
        self.ModelCombo.SelectedIndex = 0

    def _current_model(self):
        item = self.ModelCombo.SelectedItem
        return str(item.Content) if item is not None else config.DEFAULT_MODEL

    def _set_status(self, text, brush):
        self.StatusText.Text = text
        self.StatusText.Foreground = brush

    def _on_cancel(self, sender, args):
        self.Close()

    def _on_save(self, sender, args):
        key = (self.ApiKeyBox.Password or "").strip()
        if not key:
            self._set_status("API key is empty — nothing saved.", ERR_BRUSH)
            return
        try:
            user_config.set_value("anthropic_api_key", key)
            user_config.set_value("model", self._current_model())
        except Exception as e:
            self._set_status(
                "Failed to write {}: {}".format(user_config.config_path(), e),
                ERR_BRUSH,
            )
            return
        self._set_status("Saved.", OK_BRUSH)
        self.Close()

    def _on_test(self, sender, args):
        key = (self.ApiKeyBox.Password or "").strip()
        if not key:
            self._set_status("Enter an API key first.", ERR_BRUSH)
            return
        self.TestButton.IsEnabled = False
        self.SaveButton.IsEnabled = False
        self._set_status("Contacting api.anthropic.com...", INFO_BRUSH)

        def run():
            try:
                ok, msg = test_api_key(key)
            except Exception as e:
                ok, msg = False, "{}\n{}".format(e, traceback.format_exc())

            def finish():
                self._set_status(msg, OK_BRUSH if ok else ERR_BRUSH)
                self.TestButton.IsEnabled = True
                self.SaveButton.IsEnabled = True
            self.Dispatcher.Invoke(finish)

        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    SettingsWindow(XAML_PATH).ShowDialog()
