"""Thin wrappers over Revit's UnitUtils for the display-unit conversions
the tools need to do (mostly: feet -> project length unit).

Revit stores all lengths internally in decimal feet. The user thinks
in metres or millimetres. We expose two helpers so the tools layer
can stay readable.
"""

# Lazy imports — Revit API is only available inside Revit.
_cached = {}


def _imports():
    if "ok" in _cached:
        return _cached
    import clr  # noqa: F401
    clr.AddReference("RevitAPI")
    from Autodesk.Revit.DB import UnitUtils, SpecTypeId
    _cached["UnitUtils"] = UnitUtils
    _cached["SpecTypeId"] = SpecTypeId
    _cached["ok"] = True
    return _cached


def project_length_unit_id(doc):
    """ForgeTypeId for the project's length display unit."""
    m = _imports()
    fmt = doc.GetUnits().GetFormatOptions(m["SpecTypeId"].Length)
    return fmt.GetUnitTypeId()


def feet_to_project_length(doc, value_in_feet):
    m = _imports()
    return m["UnitUtils"].ConvertFromInternalUnits(
        value_in_feet, project_length_unit_id(doc)
    )


def project_length_to_feet(doc, value_in_project_units):
    m = _imports()
    return m["UnitUtils"].ConvertToInternalUnits(
        value_in_project_units, project_length_unit_id(doc)
    )


def project_length_unit_label(doc):
    """Short label for the length unit, e.g. 'mm', 'ft', 'm'."""
    try:
        m = _imports()
        from Autodesk.Revit.DB import LabelUtils
        return LabelUtils.GetLabelForUnit(project_length_unit_id(doc))
    except Exception:
        return "internal"
