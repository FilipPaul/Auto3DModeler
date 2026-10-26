# 📚 The parts library

Real parts you put into 3D models and assemblies: standard screws, nuts and washers, heat-set inserts, bearings,
standoffs, panel parts, SMC pneumatics, SICK sensors, stepper motors. Each part knows its **maker**, its **part
number** and its **order numbers**. The assembly's **⬇ BOM (CSV)** lists them, and the shop links search the part
number at the maker's shop (SMC, SICK, SKF) and at shops that fit the part (MISUMI, RS Components, Conrad, TME, Mouser,
Farnell, GM Electronic).

- `library/*.json` is the app's own library (this folder).
- `data/library/*.json` (next to `server.py`) holds **your own parts**: one file each. *📚 Save to the library* in a
  3D model's panel writes one. A part of yours with the same `id` as an app part takes its place.

Parts marked **≈ outline** are drawn from their catalogue sizes as an envelope (the front, the panel hole, the depth
behind). Check the maker's drawing before you rely on the details. The sizes of the others come from the standards
(ISO / DIN tables) or the makers' catalogues and data sheets, as their descriptions say.

## Writing a part by hand

A file holds `{"items": [ … ]}` (or one item on its own). An item:

```json
{
  "id": "my-spacer", "category": "Standoffs", "name": "Round spacer",
  "maker": "ACME", "title": "Spacer Ø{D} × {L}", "pn": "SP-{D}-{L}",
  "description": "Round spacer Ø{D} × {L} mm, hole Ø{d}",
  "color": "#c0c6cc", "material": "steel",
  "sizes": { "M3": { "d": 3.2, "D": 6 }, "M4": { "d": 4.3, "D": 8 } },
  "lengths": { "name": "Length", "values": [5, 10, 15, 20] },
  "order": { "tme": "SP{D}{L}" },
  "shape": [
    { "extrude": { "circle": { "d": "D" } }, "holes": [{ "circle": { "d": "d" } }], "z": 0, "h": "L" }
  ]
}
```

- **sizes**: the first choice. Each size's values are names you use in formulas and `{…}` texts. A size may also
  carry its own `pn`.
- **lengths**: the optional second choice (`L` in formulas). `values` is a list, or one list per size
  (`{"M3": […], …}`).
- **title / pn / description / order**: texts where `{name}` is replaced by the value.
- **approx**: `true` marks the part ≈ outline.
- **shape**: the steps, in order. A number may be a formula: `"L + k"`, `"dk / 2"`, `"max(d*0.2, 0.3)"`
  (`+ - * / ^ ( )`, `min max sqrt sin cos tan abs round`, `pi`).
  - `{"revolve": [[r, z], …]}`: a half-section, r out from the Z axis and z up, turned all the way round. Add
    `"op": "cut"` to cut it away instead.
  - `{"extrude": {shape}, "holes": [{shape}…], "z": z0, "h": height, "op": "add" | "cut", "at": [[x, y]…], "plane": "XY" | "XZ" | "YZ"}`:
    the shape (with its holes) drawn on a plane `z0` up, pushed `h` along the plane's normal (+z for XY; a negative h
    goes the other way) — for a cut too: a cut from the top face down is `"z": top, "h": -depth`. `at` repeats it at
    those points.
  - Shapes: `{"circle": {"d", "x", "y"}}`, `{"rect": {"w", "h", "x", "y", "r"}}` (x, y its middle),
    `{"hex": {"s", "x", "y"}}` (s across the flats), `{"polygon": {"n", "d", "x", "y", "turn"}}`,
    `{"polyline": [[x, y]…]}`.
  - `"when": "formula"` makes a step only where the formula is above 0 (e.g. `"top - 10"`).
  - `"color": "#rrggbb"` gives the faces that step makes their own colour (a rod, a connector); the item's `color`
    is the rest.
- The maker's real models (STEP files) attached in the library window are kept in `data/library/models.json`:
  item id -> `"size|length"` -> the stored file. The library uses that model for that choice instead of `shape`.
- Instead of `shape`, `features` may hold a 3D model's steps as they are (what *Save to the library* writes).

After a change, `py -m unittest tests.test_library` checks every file. `tools/e2e_library_build.py` builds every
part in every size.
