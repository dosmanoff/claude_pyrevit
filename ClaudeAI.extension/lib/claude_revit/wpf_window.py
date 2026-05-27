"""CPython-friendly WPF window base.

`pyrevit.forms.WPFWindow` is IronPython-only — under CPython it raises
PyRevitCPythonNotSupported. This is a tiny replacement: load XAML
through System.Windows.Markup.XamlReader and expose named elements via
`__getattr__` so callers can write `self.SendButton` instead of
`self.window.FindName("SendButton")`.

Usage:
    class MyWindow(WPFWindow):
        def __init__(self, xaml_path):
            WPFWindow.__init__(self, xaml_path)
            self.SendButton.Click += self._on_send
        def _on_send(self, sender, args):
            ...
    MyWindow(path_to_xaml).ShowDialog()
"""

import clr  # noqa: F401
clr.AddReference("PresentationFramework")
clr.AddReference("PresentationCore")
clr.AddReference("WindowsBase")
clr.AddReference("System.Xaml")

from System.Windows.Markup import XamlReader  # noqa: E402


class WPFWindow(object):
    """Load a XAML window and forward attribute access to it.

    The underlying Window object is at self.window. Anything that isn't
    explicitly set on the wrapper falls through:
      1. window.FindName(attr)   — for x:Name'd elements
      2. getattr(window, attr)   — Dispatcher, ShowDialog, Close, etc.
    """

    def __init__(self, xaml_path):
        with open(xaml_path, "r", encoding="utf-8") as f:
            xaml_text = f.read()
        self.window = XamlReader.Parse(xaml_text)

    def __getattr__(self, name):
        # __getattr__ is only called when normal lookup fails — so
        # self.window itself returns directly (it's in __dict__).
        win = self.__dict__.get("window")
        if win is None:
            raise AttributeError(name)
        elem = win.FindName(name)
        if elem is not None:
            return elem
        try:
            return getattr(win, name)
        except AttributeError:
            raise AttributeError(name)

    # Pass-through helpers — explicit so they show up in dir() and IDEs.
    def Show(self):
        self.window.Show()

    def ShowDialog(self):
        return self.window.ShowDialog()

    def Close(self):
        self.window.Close()
