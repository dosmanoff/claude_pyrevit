"""Gather a snapshot of the active Revit document for `get_revit_context`.

We keep this cheap: we don't enumerate every element, only category
counts via a single FilteredElementCollector per category in the doc.
For typical models this is fast (<1 s); on huge models we cap it.
"""

from . import units


# Max categories to enumerate counts for in one snapshot.
MAX_CATEGORIES = 60


def gather_context(doc, uidoc):
    import clr  # noqa: F401
    clr.AddReference("RevitAPI")
    from Autodesk.Revit.DB import (
        FilteredElementCollector,
        ElementMulticategoryFilter,
        BuiltInCategory,
        Category,
    )

    active_view = doc.ActiveView if doc else None

    categories_info = []
    if doc is not None:
        try:
            seen = 0
            for cat in doc.Settings.Categories:
                if seen >= MAX_CATEGORIES:
                    break
                # Only model + annotation categories that allow bound params
                if cat is None or not cat.AllowsBoundParameters:
                    continue
                try:
                    cnt = (
                        FilteredElementCollector(doc)
                        .OfCategoryId(cat.Id)
                        .WhereElementIsNotElementType()
                        .GetElementCount()
                    )
                except Exception:
                    cnt = None
                if cnt:
                    categories_info.append({
                        "name": cat.Name,
                        "count": cnt,
                    })
                    seen += 1
        except Exception as e:
            categories_info = [{"error": str(e)}]

    categories_info.sort(key=lambda r: -(r.get("count") or 0))

    try:
        length_unit = units.project_length_unit_label(doc)
    except Exception:
        length_unit = "unknown"

    return {
        "document_title": getattr(doc, "Title", None),
        "active_view_name": getattr(active_view, "Name", None),
        "active_view_type": str(getattr(active_view, "ViewType", "")),
        "project_length_unit": length_unit,
        "categories": categories_info,
    }
