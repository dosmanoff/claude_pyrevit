"""Map friendly category names to Autodesk.Revit.DB.BuiltInCategory enum
members.

We accept three forms:
  - Display name in English ("Structural Columns", "Walls", "Doors")
  - BuiltInCategory enum name ("OST_StructuralColumns")
  - Localized display name as returned by Category.Name (best effort)

Categories not in this map fall through to a runtime lookup against
Document.Settings.Categories.
"""

# Curated list of categories that are useful in NL workflows.
# Add more as needed — the runtime fallback also handles others.
COMMON_CATEGORIES = {
    "walls": "OST_Walls",
    "wall": "OST_Walls",

    "doors": "OST_Doors",
    "door": "OST_Doors",

    "windows": "OST_Windows",
    "window": "OST_Windows",

    "floors": "OST_Floors",
    "floor": "OST_Floors",

    "roofs": "OST_Roofs",
    "roof": "OST_Roofs",

    "ceilings": "OST_Ceilings",
    "ceiling": "OST_Ceilings",

    "rooms": "OST_Rooms",
    "room": "OST_Rooms",

    "areas": "OST_Areas",
    "area": "OST_Areas",

    "levels": "OST_Levels",
    "level": "OST_Levels",

    "grids": "OST_Grids",
    "grid": "OST_Grids",

    "columns": "OST_Columns",
    "column": "OST_Columns",
    "architectural columns": "OST_Columns",

    "structural columns": "OST_StructuralColumns",
    "structural column": "OST_StructuralColumns",
    "str columns": "OST_StructuralColumns",

    "structural framing": "OST_StructuralFraming",
    "beams": "OST_StructuralFraming",
    "beam": "OST_StructuralFraming",

    "structural foundations": "OST_StructuralFoundation",
    "foundations": "OST_StructuralFoundation",
    "foundation": "OST_StructuralFoundation",

    "structural rebar": "OST_Rebar",
    "rebar": "OST_Rebar",

    "stairs": "OST_Stairs",
    "stair": "OST_Stairs",

    "railings": "OST_StairsRailing",
    "railing": "OST_StairsRailing",

    "ramps": "OST_Ramps",
    "ramp": "OST_Ramps",

    "curtain walls": "OST_Walls",
    "curtain panels": "OST_CurtainWallPanels",
    "curtain mullions": "OST_CurtainWallMullions",

    "generic models": "OST_GenericModel",
    "generic model": "OST_GenericModel",

    "mass": "OST_Mass",
    "masses": "OST_Mass",

    "views": "OST_Views",
    "view": "OST_Views",
    "sheets": "OST_Sheets",
    "sheet": "OST_Sheets",

    "ducts": "OST_DuctCurves",
    "pipes": "OST_PipeCurves",
    "cable trays": "OST_CableTray",
    "conduits": "OST_Conduit",

    "electrical equipment": "OST_ElectricalEquipment",
    "electrical fixtures": "OST_ElectricalFixtures",
    "lighting fixtures": "OST_LightingFixtures",
    "mechanical equipment": "OST_MechanicalEquipment",
    "plumbing fixtures": "OST_PlumbingFixtures",

    "furniture": "OST_Furniture",
    "casework": "OST_Casework",
    "specialty equipment": "OST_SpecialityEquipment",
}


def resolve_built_in_category(name, BuiltInCategory):
    """Return a BuiltInCategory member or None.

    Tries: direct enum name, normalized common-name map, then enum-name
    fuzzy match (case-insensitive).
    """
    if not name:
        return None
    raw = str(name).strip()

    # Direct enum name, e.g. "OST_Walls"
    if raw.startswith("OST_") and hasattr(BuiltInCategory, raw):
        return getattr(BuiltInCategory, raw)

    # Curated map
    key = raw.lower()
    enum_name = COMMON_CATEGORIES.get(key)
    if enum_name and hasattr(BuiltInCategory, enum_name):
        return getattr(BuiltInCategory, enum_name)

    # Case-insensitive enum lookup
    target = ("OST_" + raw.replace(" ", "")).lower()
    for attr in dir(BuiltInCategory):
        if attr.lower() == target:
            return getattr(BuiltInCategory, attr)

    return None
