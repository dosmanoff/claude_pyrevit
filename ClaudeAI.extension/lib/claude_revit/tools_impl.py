"""Python implementations of the tools defined in tools_schema.

These are the only code paths that touch the Revit API in response to
Claude's tool calls. `dispatch(name, args, doc, uidoc)` is the entry
point the chat window uses.

Conventions:
- Element IDs are returned as the integer form (Revit 2024+ .Value /
  legacy .IntegerValue). We accept both int and string forms on input
  because Claude may serialize either way.
- Reads return primitive types Claude can reason about (strings,
  numbers, booleans). For numeric parameters we return BOTH the raw
  internal value (`value`) and the formatted display string
  (`value_display`) so the model can choose.
- Writes are limited to String and Integer storage types in this MVP.
  Double writes need explicit unit handling we haven't built yet.
"""

from . import category_map
from . import context as ctx_mod
from . import preview as preview_mod


# Cap on elements returned by query_elements. Above this we set
# truncated=True and the model is asked to narrow the query.
MAX_QUERY_RESULTS = 5000

# Cap on elements per get_element_data call. We hard-limit to keep
# response sizes (and token cost) bounded.
MAX_DATA_ELEMENTS = 1000


# ---------------------------------------------------------------- helpers


def _revit_imports():
    """Lazy import so this module is importable outside Revit (tests)."""
    import clr  # noqa: F401
    clr.AddReference("RevitAPI")
    clr.AddReference("RevitAPIUI")
    from Autodesk.Revit.DB import (
        FilteredElementCollector,
        BuiltInCategory,
        ElementId,
        Transaction,
        StorageType,
        LocationPoint,
        LocationCurve,
    )
    return {
        "FilteredElementCollector": FilteredElementCollector,
        "BuiltInCategory": BuiltInCategory,
        "ElementId": ElementId,
        "Transaction": Transaction,
        "StorageType": StorageType,
        "LocationPoint": LocationPoint,
        "LocationCurve": LocationCurve,
    }


def _eid_int(eid):
    """ElementId -> int, handling both 2024+ (.Value) and older (.IntegerValue)."""
    try:
        return int(eid.Value)
    except AttributeError:
        return int(eid.IntegerValue)


def _coerce_eid(R, value):
    """Accept int or string, return Autodesk.Revit.DB.ElementId."""
    if value is None:
        return None
    if isinstance(value, str):
        value = int(value.strip())
    return R["ElementId"](int(value))


def _read_param_value(param, R):
    """Return a dict {value, value_display, storage_type} for a parameter."""
    st = param.StorageType
    out = {"storage_type": str(st).split(".")[-1]}

    if st == R["StorageType"].String:
        out["value"] = param.AsString()
    elif st == R["StorageType"].Integer:
        out["value"] = param.AsInteger()
    elif st == R["StorageType"].Double:
        out["value"] = param.AsDouble()  # internal units (feet for length)
    elif st == R["StorageType"].ElementId:
        eid = param.AsElementId()
        out["value"] = _eid_int(eid) if eid else None
    else:
        out["value"] = None

    try:
        vs = param.AsValueString()
        if vs:
            out["value_display"] = vs
    except Exception:
        pass

    return out


def _find_param(element, name):
    """LookupParameter on the instance first, then the type."""
    p = element.LookupParameter(name)
    if p is not None:
        return p
    try:
        type_id = element.GetTypeId()
        if type_id is None:
            return None
        if _eid_int(type_id) == -1:  # ElementId.InvalidElementId
            return None
        tp = element.Document.GetElement(type_id)
        if tp is not None:
            return tp.LookupParameter(name)
    except Exception:
        return None
    return None


def _location_data(element, R):
    """Return {x, y, z, z_base, z_top} or {} if no location available."""
    loc = element.Location
    out = {}
    if loc is None:
        # Some elements (rooms, hosted) have no Location; fall back to bbox
        pass
    elif isinstance(loc, R["LocationPoint"]):
        pt = loc.Point
        out["x"] = pt.X
        out["y"] = pt.Y
        out["z"] = pt.Z
    elif isinstance(loc, R["LocationCurve"]):
        try:
            p0 = loc.Curve.GetEndPoint(0)
            out["x"] = p0.X
            out["y"] = p0.Y
            out["z"] = p0.Z
        except Exception:
            pass

    try:
        bbox = element.get_BoundingBox(None)
        if bbox is not None:
            out["z_base"] = bbox.Min.Z
            out["z_top"] = bbox.Max.Z
    except Exception:
        pass

    try:
        lvl_id = element.LevelId
        if lvl_id is not None and _eid_int(lvl_id) != -1:
            lvl = element.Document.GetElement(lvl_id)
            if lvl is not None:
                out["level_name"] = lvl.Name
                try:
                    out["level_elevation"] = lvl.Elevation
                except Exception:
                    pass
    except Exception:
        pass

    return out


# ---------------------------------------------------------------- tools


def tool_get_revit_context(args, doc, uidoc):
    return ctx_mod.gather_context(doc, uidoc)


def tool_query_elements(args, doc, uidoc):
    R = _revit_imports()
    category_name = args.get("category")
    view_only = bool(args.get("view_only", False))

    bic = category_map.resolve_built_in_category(category_name, R["BuiltInCategory"])
    if bic is None:
        return {
            "error": "Unknown category: {!r}. Try a Revit display name like "
                     "'Structural Columns' or a BuiltInCategory name like "
                     "'OST_StructuralColumns'.".format(category_name)
        }

    if view_only and doc.ActiveView is not None:
        col = R["FilteredElementCollector"](doc, doc.ActiveView.Id)
    else:
        col = R["FilteredElementCollector"](doc)
    col = col.OfCategory(bic).WhereElementIsNotElementType()

    ids = []
    truncated = False
    for el in col:
        ids.append(_eid_int(el.Id))
        if len(ids) >= MAX_QUERY_RESULTS:
            truncated = True
            break

    return {
        "category": category_name,
        "view_only": view_only,
        "count": len(ids),
        "truncated": truncated,
        "element_ids": ids,
    }


def tool_get_element_data(args, doc, uidoc):
    R = _revit_imports()
    raw_ids = args.get("element_ids") or []
    if len(raw_ids) > MAX_DATA_ELEMENTS:
        return {
            "error": "Too many elements requested ({}). Max per call is {}. "
                     "Split into batches.".format(len(raw_ids), MAX_DATA_ELEMENTS)
        }

    params_wanted = args.get("parameters") or []
    include_location = bool(args.get("include_location", False))

    records = []
    missing_params = set()
    for raw in raw_ids:
        try:
            el_id = _coerce_eid(R, raw)
            element = doc.GetElement(el_id)
        except Exception as e:
            records.append({"element_id": raw, "error": "id parse: {}".format(e)})
            continue
        if element is None:
            records.append({"element_id": raw, "error": "not found"})
            continue

        rec = {
            "element_id": _eid_int(element.Id),
            "category": getattr(getattr(element, "Category", None), "Name", None),
        }
        try:
            rec["type_name"] = doc.GetElement(element.GetTypeId()).Name
        except Exception:
            pass

        if params_wanted:
            pvals = {}
            for pname in params_wanted:
                p = _find_param(element, pname)
                if p is None:
                    pvals[pname] = None
                    missing_params.add(pname)
                else:
                    pvals[pname] = _read_param_value(p, R)
            rec["parameters"] = pvals

        if include_location:
            rec["location"] = _location_data(element, R)

        records.append(rec)

    return {
        "count": len(records),
        "records": records,
        "missing_params": sorted(missing_params),
    }


def _set_one_param(element, pname, value, R):
    p = _find_param(element, pname)
    if p is None:
        return "parameter '{}' not found".format(pname)
    if p.IsReadOnly:
        return "parameter '{}' is read-only".format(pname)
    st = p.StorageType
    try:
        if st == R["StorageType"].String:
            p.Set("" if value is None else str(value))
        elif st == R["StorageType"].Integer:
            if isinstance(value, bool):
                p.Set(1 if value else 0)
            else:
                p.Set(int(value))
        elif st == R["StorageType"].Double:
            # MVP: refuse Double writes — we don't have unit info here.
            return ("parameter '{}' is a Double (length/area/etc.) — Double "
                    "writes not supported in MVP".format(pname))
        elif st == R["StorageType"].ElementId:
            p.Set(_coerce_eid(R, value))
        else:
            return "unsupported storage type"
    except Exception as e:
        return "set failed: {}".format(e)
    return None


def tool_set_parameter_values(args, doc, uidoc):
    R = _revit_imports()
    description = args.get("description") or "Apply parameter changes"
    updates = args.get("updates") or []
    if not updates:
        return {"applied": 0, "cancelled": False, "errors": ["no updates provided"]}

    # 1) Look up current values for the preview
    before_lookup = {}
    for u in updates:
        try:
            eid = _coerce_eid(R, u["element_id"])
            el = doc.GetElement(eid)
            if el is None:
                continue
            p = _find_param(el, u["parameter"])
            if p is None:
                continue
            data = _read_param_value(p, R)
            before_lookup[(str(u["element_id"]), u["parameter"])] = (
                data.get("value_display") or data.get("value")
            )
        except Exception:
            continue

    # 2) Ask the user
    if not preview_mod.confirm_changes(description, updates, before_lookup):
        return {"applied": 0, "cancelled": True, "errors": []}

    # 3) Apply in a single transaction
    errors = []
    applied = 0
    t = R["Transaction"](doc, "Claude: " + description[:120])
    try:
        t.Start()
        for u in updates:
            try:
                eid = _coerce_eid(R, u["element_id"])
                el = doc.GetElement(eid)
                if el is None:
                    errors.append({"element_id": u["element_id"], "error": "not found"})
                    continue
                err = _set_one_param(el, u["parameter"], u["value"], R)
                if err:
                    errors.append({
                        "element_id": u["element_id"],
                        "parameter": u["parameter"],
                        "error": err,
                    })
                else:
                    applied += 1
            except Exception as e:
                errors.append({
                    "element_id": u.get("element_id"),
                    "parameter": u.get("parameter"),
                    "error": str(e),
                })
        t.Commit()
    except Exception as e:
        try:
            t.RollBack()
        except Exception:
            pass
        return {
            "applied": 0,
            "cancelled": False,
            "errors": [{"transaction": str(e)}],
        }

    return {"applied": applied, "cancelled": False, "errors": errors}


# ---------------------------------------------------------------- dispatch


_DISPATCH = {
    "get_revit_context": tool_get_revit_context,
    "query_elements": tool_query_elements,
    "get_element_data": tool_get_element_data,
    "set_parameter_values": tool_set_parameter_values,
}


def dispatch(tool_name, tool_input, doc, uidoc):
    fn = _DISPATCH.get(tool_name)
    if fn is None:
        return {"error": "unknown tool: {}".format(tool_name)}
    return fn(tool_input or {}, doc, uidoc)
