# claude_revit — shared library for the Claude AI pyRevit extension.
#
# Modules:
#   config        — API key and model selection.
#   api_client    — HTTP client for Anthropic Messages API.
#   system_prompt — system prompt + tool descriptions.
#   tools_schema  — JSON schemas Claude sees.
#   tools_impl    — Python implementations that touch the Revit API.
#   context       — gather current-doc context for the system prompt.
#   preview       — preview-and-confirm dialog for write operations.
#   units         — Revit-internal-units <-> display-units conversion.
#   category_map  — friendly category name <-> BuiltInCategory.

__version__ = "0.1.0"
