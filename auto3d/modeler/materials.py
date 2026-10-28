"""The materials a part can be of -> density (g/cm³), the colour a part of it is shown in and how its surface looks
(metalness, roughness: glTF), as in web/js/modeler/materials.js."""

DENSITY = {
    "PLA": 1.24,
    "PETG": 1.27,
    "ABS": 1.04,
    "ASA": 1.07,
    "TPU": 1.21,
    "PA": 1.14,
    "PA-CF": 1.2,
    "PC": 1.2,
    "PP": 0.9,
    "POM": 1.41,
    "PE-HD": 0.95,
    "PA6-GF30": 1.36,
    "PTFE": 2.2,
    "PEEK": 1.32,
    "PMMA": 1.18,
    "PVC": 1.38,
    "aluminium": 2.7,
    "aluminium 7075": 2.81,
    "steel": 7.85,
    "steel C45": 7.85,
    "stainless steel": 7.93,
    "stainless steel 316": 8.0,
    "tool steel": 7.8,
    "cast iron": 7.2,
    "brass": 8.5,
    "bronze": 8.8,
    "copper": 8.96,
    "titanium": 4.43,
    "zinc die-cast": 6.6,
    "magnesium": 1.8,
    "rubber (EPDM)": 1.15,
    "silicone": 1.15,
    "plywood": 0.6,
    "MDF": 0.75,
    "glass": 2.5,
    "carbon fibre (CFRP)": 1.6,
    "FR4 (PCB)": 1.85,
}

NAMES = list(DENSITY)

COLOR = {
    "PLA": "#d6dbe3", "PETG": "#9cc7d6", "ABS": "#ece6d6", "ASA": "#dcdcd4", "TPU": "#3d3d3d", "PA": "#ece4d2", "PA-CF": "#2e2e2e",
    "PC": "#cfd8dc", "PP": "#f0eee4", "POM": "#f4f4ef", "PE-HD": "#f2f2ea", "PA6-GF30": "#2b2b2b", "PTFE": "#f8f8f6", "PEEK": "#c9ab72",
    "PMMA": "#cfe7ef", "PVC": "#9a9fa4", "aluminium": "#c3c8cd", "aluminium 7075": "#b4bac1", "steel": "#8b9097", "steel C45": "#7f858c",
    "stainless steel": "#bcc1c6", "stainless steel 316": "#c4c9ce", "tool steel": "#6f747a", "cast iron": "#5e6063", "brass": "#c9a64b",
    "bronze": "#a2753b", "copper": "#b87333", "titanium": "#8f9095", "zinc die-cast": "#a9aeb4", "magnesium": "#b5babf",
    "rubber (EPDM)": "#2a2a2a", "silicone": "#e8e2d6", "plywood": "#c9a46c", "MDF": "#b58c5e", "glass": "#d6ebf1",
    "carbon fibre (CFRP)": "#262626", "FR4 (PCB)": "#2f6b3a",
}

# how a material's surface looks: (metalness, roughness) — metals metallic, the rest not (materials.js FINISH)
FINISH = {
    "aluminium": (0.9, 0.38), "aluminium 7075": (0.9, 0.36), "steel": (0.85, 0.42), "steel C45": (0.85, 0.45), "stainless steel": (0.95, 0.24),
    "stainless steel 316": (0.95, 0.22), "tool steel": (0.85, 0.35), "cast iron": (0.7, 0.62), "brass": (0.95, 0.28), "bronze": (0.9, 0.36),
    "copper": (0.95, 0.3), "titanium": (0.85, 0.4), "zinc die-cast": (0.8, 0.45), "magnesium": (0.75, 0.5),
    "glass": (0, 0.06), "PMMA": (0, 0.12), "PC": (0, 0.25), "rubber (EPDM)": (0, 0.9), "silicone": (0, 0.8), "TPU": (0, 0.8), "plywood": (0, 0.8),
    "MDF": (0, 0.85),
}


def finish_of(material):
    """(metalness, roughness) of a material's surface; not chosen: a plain plastic (materials.js finishOf)."""
    return FINISH.get(material or "", (0.05, 0.55))


def look_colour(part):
    """A part's colour as shown: its own, else its material's (when one was chosen), else None (materials.js lookColor)."""
    return (part or {}).get("color") or COLOR.get((part or {}).get("material") or "")


# the 3D printing plastics (materials.js: its first group) — a part of one is "made (3D print)", of the rest "made"
PRINTED = {"PLA", "PETG", "ABS", "ASA", "TPU", "PA", "PA-CF", "PC", "PP"}


def made_how(row):
    """A BOM row's "Bought / made": bought (a library part), made (3D print) (a printing plastic; none chosen: PLA) or
    made (a metal, an engineering plastic …) — as the browser's bomFlat."""
    if row.get("library"):
        return "bought"
    return "made (3D print)" if (row.get("material") or "PLA") in PRINTED else "made"
