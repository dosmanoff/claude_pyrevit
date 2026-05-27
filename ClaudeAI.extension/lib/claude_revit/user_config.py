"""Per-user settings, stored OUTSIDE the repository.

Location: %APPDATA%/claude_pyrevit/config.json on Windows,
~/.claude_pyrevit/config.json elsewhere.

This is what the in-Revit Settings dialog reads and writes. The file
itself is plain JSON; if it doesn't exist, every getter returns None.

Keep the schema small and forward-compatible: unknown keys are
preserved by load+save round-trips.
"""

import json
import os


CONFIG_DIRNAME = "claude_pyrevit"
CONFIG_FILENAME = "config.json"


def config_dir():
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, CONFIG_DIRNAME)
    return os.path.join(os.path.expanduser("~"), "." + CONFIG_DIRNAME)


def config_path():
    return os.path.join(config_dir(), CONFIG_FILENAME)


def load():
    """Return the full settings dict, or {} if no file."""
    path = config_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save(data):
    """Write the full settings dict. Creates the directory if missing."""
    if not isinstance(data, dict):
        raise TypeError("user_config.save expects a dict")
    d = config_dir()
    if not os.path.isdir(d):
        os.makedirs(d)
    path = config_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def get(key, default=None):
    return load().get(key, default)


def set_value(key, value):
    data = load()
    if value is None:
        data.pop(key, None)
    else:
        data[key] = value
    save(data)
    return data


# Convenience accessors used by the rest of the extension.

def api_key():
    return get("anthropic_api_key")


def model():
    return get("model")
