#! python3
# -*- coding: utf-8 -*-
"""Entry point for the Claude chat button.

Loads ChatWindow.xaml, wires up Send/Clear, drives the Anthropic
tool-use loop on a background thread, and routes tool calls back to
the UI thread (where the Revit API is valid).
"""

import os
import threading
import traceback

import clr  # noqa: F401
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")

from System.Windows.Controls import TextBlock
from System.Windows.Documents import Run
from System.Windows.Media import SolidColorBrush
from System.Windows.Media import Color as WpfColor
from System.Windows import Thickness, FontWeights, TextWrapping

from claude_revit.wpf_window import WPFWindow

from claude_revit.api_client import run_turn, AnthropicError
from claude_revit.system_prompt import SYSTEM_PROMPT
from claude_revit.tools_schema import TOOLS
from claude_revit import tools_impl
from claude_revit import config


XAML_PATH = os.path.join(os.path.dirname(__file__), "ChatWindow.xaml")

# __revit__ is injected by pyRevit into every script's globals.
UIDOC = __revit__.ActiveUIDocument  # noqa: F821
DOC = UIDOC.Document if UIDOC is not None else None

USER_BRUSH = SolidColorBrush(WpfColor.FromRgb(33, 99, 169))
ASSISTANT_BRUSH = SolidColorBrush(WpfColor.FromRgb(40, 40, 40))
TOOL_BRUSH = SolidColorBrush(WpfColor.FromRgb(120, 120, 120))
ERROR_BRUSH = SolidColorBrush(WpfColor.FromRgb(180, 50, 50))


class ChatWindow(WPFWindow):

    def __init__(self, xaml_path):
        WPFWindow.__init__(self, xaml_path)
        self.messages = []
        self.usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }
        self.busy = False

        self.SendButton.Click += self._on_send_clicked
        self.ClearButton.Click += self._on_clear_clicked

        if not config.get_api_key():
            self._append("Setup", (
                "No API key set. Click the Settings button next to this one "
                "and paste your Anthropic API key (sk-ant-...). The key is "
                "stored at %APPDATA%\\claude_pyrevit\\config.json, not in "
                "the repository."
            ), ERROR_BRUSH)
        else:
            self._append("Claude", (
                "Hi! Describe what you want to do in Revit. I'll always show "
                "you a preview before changing anything."
            ), ASSISTANT_BRUSH)

    # ---------------------------------------------------------- UI helpers

    def _append(self, who, text, brush):
        block = TextBlock()
        block.TextWrapping = TextWrapping.Wrap
        block.Margin = Thickness(0, 4, 0, 8)
        block.FontSize = 13

        head = Run(who + ":  ")
        head.FontWeight = FontWeights.Bold
        head.Foreground = brush
        block.Inlines.Add(head)

        body = Run(text)
        body.Foreground = brush if who in ("You", "Error") else ASSISTANT_BRUSH
        block.Inlines.Add(body)

        self.ChatLog.Children.Add(block)
        self.ChatScroll.ScrollToBottom()

    def _set_status(self, text):
        self.StatusText.Text = text

    def _update_tokens(self):
        self.TokensText.Text = (
            "tokens: {} in / {} out  cache: {}r / {}w".format(
                self.usage["input_tokens"],
                self.usage["output_tokens"],
                self.usage["cache_read_input_tokens"],
                self.usage["cache_creation_input_tokens"],
            )
        )

    def _accumulate_usage(self, partial):
        for k, v in (partial or {}).items():
            if k in self.usage:
                self.usage[k] += v or 0
        self._update_tokens()

    def _ui(self, action):
        """Marshal a no-arg callable onto the WPF dispatcher (UI thread)."""
        self.Dispatcher.Invoke(action)

    # ------------------------------------------------------------ handlers

    def _on_clear_clicked(self, sender, args):
        if self.busy:
            return
        self.messages = []
        self.ChatLog.Children.Clear()
        self._append("Claude", "Conversation cleared.", ASSISTANT_BRUSH)

    def _on_send_clicked(self, sender, args):
        if self.busy:
            return
        text = (self.InputBox.Text or "").strip()
        if not text:
            return
        if not config.get_api_key():
            self._append("Error", "No API key set.", ERROR_BRUSH)
            return

        self.InputBox.Text = ""
        self._append("You", text, USER_BRUSH)
        self.messages.append({"role": "user", "content": text})

        self.busy = True
        self.SendButton.IsEnabled = False
        self.ClearButton.IsEnabled = False
        self._set_status("Thinking...")

        t = threading.Thread(target=self._run_turn_bg, daemon=True)
        t.start()

    # ------------------------------------------------------ background work

    def _make_dispatcher(self):
        """Tool dispatcher that runs the actual Revit work on the UI thread."""
        def dispatcher(tool_name, tool_input):
            holder = {"result": None, "error": None}

            def on_ui():
                try:
                    holder["result"] = tools_impl.dispatch(
                        tool_name, tool_input, DOC, UIDOC
                    )
                except Exception as e:
                    holder["error"] = "{}\n{}".format(e, traceback.format_exc())

            self.Dispatcher.Invoke(on_ui)
            if holder["error"]:
                raise RuntimeError(holder["error"])
            return holder["result"]
        return dispatcher

    def _on_progress(self, stage, detail):
        self._ui(lambda: self._set_status("{}: {}".format(stage, detail)))

    def _run_turn_bg(self):
        try:
            result = run_turn(
                messages=self.messages,
                system_prompt=SYSTEM_PROMPT,
                tools_schema=TOOLS,
                tool_dispatcher=self._make_dispatcher(),
                on_progress=self._on_progress,
            )
        except AnthropicError as e:
            self._ui(lambda: self._append("Error", str(e), ERROR_BRUSH))
            self._ui(lambda: self._set_status("Error"))
            self._ui(self._reset_busy)
            return
        except Exception as e:
            tb = traceback.format_exc()
            self._ui(lambda: self._append("Error", "{}\n{}".format(e, tb), ERROR_BRUSH))
            self._ui(lambda: self._set_status("Error"))
            self._ui(self._reset_busy)
            return

        def finish():
            if result["text"]:
                self._append("Claude", result["text"], ASSISTANT_BRUSH)
            self._accumulate_usage(result["usage_total"])
            self._set_status(
                "Ready  ·  rounds: {}  ·  stop: {}".format(
                    result["rounds"], result["stopped_by"]
                )
            )
            self._reset_busy()
        self._ui(finish)

    def _reset_busy(self):
        self.busy = False
        self.SendButton.IsEnabled = True
        self.ClearButton.IsEnabled = True
        self.InputBox.Focus()


if __name__ == "__main__":
    window = ChatWindow(XAML_PATH)
    window.ShowDialog()
