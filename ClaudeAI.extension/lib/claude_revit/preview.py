"""Preview-and-confirm dialog for write operations.

We use Revit's TaskDialog (no extra XAML, no extra dependency) and
render the updates as a tab-aligned text table. For very long lists we
truncate the visible rows but the actual write still applies to all.

The dialog is *modal* and called from the chat window which is itself
modeless — but `set_parameter_values` is invoked from the tool dispatch
loop which runs on the UI thread inside a valid API context, so showing
a TaskDialog here is safe.
"""

MAX_PREVIEW_ROWS = 80


def _format_value(v):
    if v is None:
        return "<null>"
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        # Trim trailing zeros for readability
        return ("{:.6f}".format(v)).rstrip("0").rstrip(".")
    return str(v)


def _format_table(rows, before_lookup):
    """rows: list of {element_id, parameter, value}
    before_lookup: dict {(eid, param): current_value}
    """
    lines = ["{:>10} | {:<30} | {:<24} -> {:<24}".format(
        "ElementId", "Parameter", "Current", "New"
    )]
    lines.append("-" * 100)
    shown = rows[:MAX_PREVIEW_ROWS]
    for r in shown:
        eid = r["element_id"]
        param = r["parameter"]
        new_val = _format_value(r["value"])
        cur = _format_value(before_lookup.get((str(eid), param), None))
        # truncate cells
        param = param[:30]
        cur = cur[:24]
        new_val = new_val[:24]
        lines.append("{:>10} | {:<30} | {:<24} -> {:<24}".format(
            eid, param, cur, new_val
        ))
    if len(rows) > MAX_PREVIEW_ROWS:
        lines.append("... and {} more rows".format(len(rows) - MAX_PREVIEW_ROWS))
    return "\n".join(lines)


def confirm_changes(description, rows, before_lookup):
    """Show the preview dialog. Returns True if user clicked Apply, else False."""
    import clr  # noqa: F401
    clr.AddReference("RevitAPIUI")
    from Autodesk.Revit.UI import (
        TaskDialog, TaskDialogCommonButtons, TaskDialogResult
    )

    td = TaskDialog("Claude — preview changes")
    td.MainInstruction = description or "Apply these {} changes?".format(len(rows))
    td.MainContent = _format_table(rows, before_lookup)
    td.CommonButtons = TaskDialogCommonButtons.Yes | TaskDialogCommonButtons.No
    td.DefaultButton = TaskDialogResult.No

    result = td.Show()
    return result == TaskDialogResult.Yes
