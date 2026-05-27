"""Runtime config — API key and model selection.

Resolution order (first hit wins):
  1. user_config.json   — set via the in-Revit Settings dialog.
                          Stored under %APPDATA%/claude_pyrevit/.
  2. ANTHROPIC_API_KEY  — environment variable.
  3. _local_config.py   — dev-only override, gitignored.

For typical desktop installs (1) is what the user interacts with.
"""

import os

from . import user_config

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8192
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"

# How many tool-use rounds we allow in a single user turn before giving up.
# Each round is one HTTP call; this caps runaway loops.
MAX_TOOL_ROUNDS = 20


def _from_local_config(attr):
    try:
        from . import _local_config  # type: ignore
    except ImportError:
        return None
    return getattr(_local_config, attr, None)


def get_api_key():
    key = user_config.api_key()
    if key:
        return key
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    return _from_local_config("ANTHROPIC_API_KEY")


def get_model():
    return (
        user_config.model()
        or _from_local_config("MODEL")
        or DEFAULT_MODEL
    )


def api_key_source():
    """Where did the current API key come from? Used by the Settings UI."""
    if user_config.api_key():
        return "user_config"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "env"
    if _from_local_config("ANTHROPIC_API_KEY"):
        return "local_config"
    return None
