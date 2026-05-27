"""JSON schemas for the tools that Claude is allowed to call.

Design rules:

- Element identity is always Revit's integer ElementId (or the string form
  for Revit 2024+ where IntegerValue is deprecated — we accept both).
- All write operations go through `set_parameter_values`, which always
  shows a preview to the user. There is no "commit without preview" path.
- Tools that return potentially-large lists return a `truncated` flag and
  a summary instead of dumping thousands of rows blindly.
"""

TOOLS = [
    {
        "name": "get_revit_context",
        "description": (
            "Return a snapshot of the active Revit document: title, active "
            "view name + view type, project units (length, angle), and a "
            "list of element categories present in the document with their "
            "instance counts. Call this once at the start of a task so you "
            "know what's available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "query_elements",
        "description": (
            "Find elements by category. Returns the list of element IDs "
            "and a count. Use `view_only=true` to limit to the active view "
            "(useful for 'this view only' tasks). For very large results, "
            "the response includes a `truncated` flag and you should narrow "
            "the query (e.g. by switching to view_only)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": (
                        "Category name. Accepts both Revit display names "
                        "('Structural Columns', 'Walls') and BuiltInCategory "
                        "names ('OST_StructuralColumns', 'OST_Walls')."
                    ),
                },
                "view_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "Limit to elements visible in the active view.",
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "get_element_data",
        "description": (
            "Read parameter values and (optionally) location data for the "
            "given elements. Returns a list of records, one per element. "
            "Location data includes `x`, `y`, `z` of the location point in "
            "project display units, plus `level_name` and `level_elevation` "
            "for level-hosted elements. For columns and other vertical "
            "elements, `z_base` and `z_top` are also returned when available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "element_ids": {
                    "type": "array",
                    "items": {"type": ["integer", "string"]},
                    "description": "Element IDs returned by query_elements.",
                },
                "parameters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Parameter display names to read. Both instance and "
                        "type parameters are searched. Unknown parameters "
                        "come back as null with a note in `missing_params`."
                    ),
                },
                "include_location": {
                    "type": "boolean",
                    "default": False,
                },
            },
            "required": ["element_ids"],
        },
    },
    {
        "name": "set_parameter_values",
        "description": (
            "Write parameter values to elements. ALWAYS show the user a "
            "preview by calling this — the implementation pops up a "
            "preview dialog and only writes if the user confirms. Returns "
            "{applied: N, cancelled: bool, errors: [...]}. Wrap the entire "
            "batch in one description so the user sees what's happening."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": (
                        "One-sentence summary shown above the preview, "
                        "e.g. 'Set Mark on 12 columns following C{loc}.{n} "
                        "pattern'."
                    ),
                },
                "updates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "element_id": {"type": ["integer", "string"]},
                            "parameter": {"type": "string"},
                            "value": {
                                "description": (
                                    "New value. Strings, numbers, and "
                                    "booleans are accepted; the impl casts "
                                    "to the parameter's storage type."
                                ),
                            },
                        },
                        "required": ["element_id", "parameter", "value"],
                    },
                },
            },
            "required": ["description", "updates"],
        },
    },
]
