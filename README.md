# claude_pyrevit

A pyRevit extension that lets you drive Revit 2025 with natural-language
commands through Anthropic's Claude API.

Type a request like:

> Set Mark on every column as `C{Location number}.{N}` where N is the
> column's order from bottom to top within its Location number group.

Claude figures out which Revit elements to look at, gathers the data it
needs, computes the new values, shows you a preview, and applies the
change inside a single Revit transaction (so Ctrl+Z still works).

## Status

MVP scaffold. Not yet packaged or signed. Use against test models only.

## How it works

Claude does **not** generate and run code against your model. Instead it
calls a small set of whitelisted *tools*:

| Tool                   | What it does                                            |
| ---------------------- | ------------------------------------------------------- |
| `get_revit_context`    | Reports active doc, view, units, available categories.  |
| `query_elements`       | FilteredElementCollector by category / view.            |
| `get_element_data`     | Reads parameter values and locations for given IDs.     |
| `set_parameter_values` | Writes parameters — **only after user confirms preview**. |

All writes go through a preview dialog. All writes happen inside one
`Transaction`, so the user can undo with Ctrl+Z.

## Install

1. Install [pyRevit 5](https://github.com/pyrevitlabs/pyRevit/releases)
   for Revit 2025 (pyRevit 4.x does not support Revit 2025).
2. Clone this repo somewhere, e.g.
   `C:\pyRevit-Extensions\claude_pyrevit\`.
3. In Revit: pyRevit tab → Settings → Custom Extension Directories →
   add the folder that *contains* `ClaudeAI.extension`. Reload.
4. In Revit: **Smart Tools → Claude → Settings**. Paste your Anthropic
   API key (`sk-ant-...`), pick a model, hit *Test connection*, then *Save*.
   The key is stored at `%APPDATA%\claude_pyrevit\config.json` — outside
   this repository, so it never gets committed.

The extension adds buttons to the existing **Smart Tools** tab if you
already have one; otherwise pyRevit creates the tab. If your tab folder
is named differently (e.g. `Smart_Tools.tab`), rename
`ClaudeAI.extension/SmartTools.tab` to match.

### Alternate ways to provide the API key

For dev workflows you can skip the Settings dialog and use either:
- Environment variable: `setx ANTHROPIC_API_KEY sk-ant-...`
- File: create `ClaudeAI.extension/lib/claude_revit/_local_config.py`
  with `ANTHROPIC_API_KEY = "sk-ant-..."`. Gitignored.

The Settings dialog's value takes precedence over both.

## Use

In Revit: **Smart Tools** tab → **Claude** panel → **Chat** button.

Type your request. Claude will ask follow-up questions if needed and
will always show you a preview before changing anything.

## Costs

Every turn sends the conversation, the tool schema, and the gathered
element data to Claude. Big selections = more tokens. The status bar
in the chat window shows tokens per turn so you can watch spend.

Prompt caching is on by default for the system prompt and tool schemas.

## License

MIT (see LICENSE — TODO).
