"""API key, model selection, and other settings.

Resolution order for the API key:
  1. _local_config.py  (gitignored, user-edited; preferred for desktop install)
  2. ANTHROPIC_API_KEY environment variable
  3. None — caller must show an error to the user.
"""

import os

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8192
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"

# How many tool-use rounds we allow in a single user turn before giving up.
# Each round is one HTTP call; this caps runaway loops.
MAX_TOOL_ROUNDS = 20


def get_api_key():
    try:
        from . import _local_config  # type: ignore
        key = getattr(_local_config, "ANTHROPIC_API_KEY", None)
        if key:
            return key
    except ImportError:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def get_model():
    try:
        from . import _local_config  # type: ignore
        return getattr(_local_config, "MODEL", DEFAULT_MODEL)
    except ImportError:
        return DEFAULT_MODEL
