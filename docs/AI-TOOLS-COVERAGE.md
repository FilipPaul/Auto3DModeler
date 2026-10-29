# Can the AI do what the GUI does? (2026-10-29)

Every user-facing capability of the app against the AI (Claude through the app's MCP tools,
`auto3d/agent_tools.py`). GUI names in Czech in brackets.

**Status**: **ok** — a tool does it · **partial** — a tool does most of it, or another way gets there ·
**gui** — only through `gui_action` (the AI clicks the control as the user would; fine for rare or
layout-only things) · **n/a** — nothing for an AI to do there. "Was" = before this check, when it differs.

**Counts** (90 rows): before — ok 54, partial 14, gui only 21, n/a 1 (9 of the gui-only ones things an AI
designer needs: demos, opening and saving project files, switching variants, taking a part from one, the missing
joint, the trace, 📌 fixed, a solid from a file); now — **ok 64, partial 13, gui 12** (layout or rare), n/a 1.

**Wiring is tested**: `tests/test_agent_wiring.py` reads the page's handlers from the JS and checks them against
`TOOLS` both ways, the server's own tools, the real MCP server's `tools/list` (Claude Code is allowed
`mcp__auto3d` as a whole, so a new tool needs no permission change), a chat label for each tool and that a skill
or the system prompt names it. `tools/e2e_agent.py` also asks the running page for its handlers.
The check found 12 tools the chat showed by their raw name and 3 no skill named — fixed.

## Project, files, versions

| Capability | GUI place | AI tool | Status |
| --- | --- | --- | --- |
| New 3D model | top bar (＋ Nový 3D model) | `new_model` | ok |
| Open a drawing / picture / CAD / PCB file | 📂 Open ▾ (📂 Otevřít ▾) | `open_file`, `trace_picture` + `use_outline` | ok |
| Open a saved project (.a3d.json) | 📂 Open ▾ (📂 Otevřít ▾) | `open_file` | ok (was gui) |
| Sample drawing | (Ukázkový výkres) | `open_sample` | ok |
| Demo projects | 📂 Open ▾ → (🎬 Demo projekty…) | `list_demos`, `open_demo` | ok (was gui) |
| Recent projects | (🕘 Nedávné projekty…) | — | gui (the user's own list) |
| Save the project to a file | (Uložit projekt) | `export {format: "project", history}` | ok (was gui) |
| Export STL / STEP / IGES / GLB / OBJ / PDF / 3MF / BOM / DXF | (Export ▾) | `export` | ok |
| Part tabs: list, open, rename, duplicate, delete | tabs, ☰, part panel (⧉ Duplikovat jako nový díl) | `list_parts`, `open_part`, `rename_part`, `duplicate_part`, `delete_part` | ok |
| A part in a window of its own | ⧉ | — | gui (layout) |
| Undo / redo | ↶ ↷ | `undo`; redo by `gui_action {key: "ctrl+y"}` | partial |
| Language CZ / EN | CZ | — | gui (layout) |
| Parameters: make, change, delete, where used | (𝑥 Parametry) | `get_parameters`, `set_parameter {delete}` | ok |
| Versions: list, save, compare, restore, new variant | (🕘 Verze) | `list_versions`, `save_version`, `compare_versions`, `restore_version`, `create_variant` | ok |
| Switch variant | (Varianta ▾) | `switch_variant` | ok (was gui) |
| Take a part from a variant | (Převzít díl z varianty…) | `take_part` | ok (was gui) |
| Preview a version | 🕘 timeline row | `compare_versions` | partial (text, not the picture) |
| Parts library: search, put in, keep a model | (📚 Knihovna), (📚 Uložit do knihovny) | `library_search`, `library_add`, `save_to_library` | ok |
| Problem reports | ✨ AI | `report_problem`, `list_reports` | ok |
| Teach the user where to click | — | `gui_state`, `gui_highlight`, `ask_user` | ok |

## Quick part (picture, PDF drawing, import) and 3D print

| Capability | GUI place | AI tool | Status |
| --- | --- | --- | --- |
| Dimensions, point dimensions | panel, (＋ Kóta) | `set_dimensions`, `add_dimension` | ok |
| Measure | (📏 Měřit) | `get_part` (size, z levels) | partial |
| What to make: cutter / solid / custom | 3D design panel | `set_make` | ok |
| Clean-up, mirror, aspect lock, import orientation | panel | `set_part_options` | ok |
| 3D objects, 2D shapes, design layers | (＋ Díra, ＋ Text, ＋ Obrys …) | `add_object`, `add_shape`, `add_design_layer`, `update_item`, `remove_item` | ok |
| Bending: fold lines, roll | (＋ Linie ohybu, ＋ Stočit) | — | gui (rare; clicks on the part) |
| Outline editor | (✎ Upravit obrys) | `trace_picture` hints | partial |
| To a 3D model | (◆ Do 3D modelu) | — (a DXF: `drawing_use {as: "sketch"}`) | gui |
| Printer fit, pieces when split | 3D print panel | `check_print {printer, split}` | ok |
| Split joints (dovetail, dowels …), pieces ZIP, ＋ new printer | 3D print panel (Rozdělit pro tuto tiskárnu) | — | gui (many inputs) |
| A 3D model's printing copy | (🖨 Připravit pro 3D tisk) | `prepare_print`, `check_print` | ok |

## 2D drawing (DXF / DWG / PCB)

| Capability | GUI place | AI tool | Status |
| --- | --- | --- | --- |
| Layers: show, hide, colour, new, active | Layers (Hladiny) | `drawing_layers`, `get_drawing` | ok |
| Select by filter, delete | (Výběr filtrem) | `drawing_find`, `drawing_delete` | ok |
| Draw lines / circles, one size for many | (／ Čára, ◯ Kružnice) | `drawing_add`, `drawing_set_size` | ok |
| File units | (Jednotky souboru) | `drawing_units` | ok |
| Use as a sketch / a quick part | (Použít ▾) | `drawing_use` | ok |
| Pick single shapes by click | the view | `drawing_find` / `gui_action {at}` | partial |

## Sketch

| Capability | GUI place | AI tool | Status |
| --- | --- | --- | --- |
| Rectangle, circle, slot, lines, arc, spline | (▭ Obdélník, ◯ Kružnice, ⊂⊃ Drážka, ⟋ Čára, ◠ Oblouk, 〰 Spline) | `add_feature sketch` shapes (rect, circle, slot, polyline, profile with arc / smooth) | ok |
| Plane, face, offset plane, midway, origin | Sketch on… (⇳ Uprostřed, ↕ Rovina ve) | `add_feature sketch {plane}` | ok |
| Trim, union, simplify / join / merge | (✂ Oříznout, ⛓ Sloučit) | `sketch_trim`, `sketch_union`, `simplify_sketch` | ok |
| Pattern in a sketch | (⁂ Pole) | shape `pattern {count, spacing / around}` | ok |
| Dimensions, auto-dimension | (↔ Kóta, 🪄 Automatické kóty) | `get_sketch`, `sketch_dim`, `sketch_auto_dims` | ok |
| Relations | (⟂ Vazby ▾) | `get_sketch` reads them, `sketch_auto_dims` adds the near ones | partial |
| Round corner | (◜ Zaoblit roh) | rect `r`, profile arcs | partial |
| Text in a sketch | (𝐓 Text) | `add_feature decal` (text on a face) | partial |
| Outline from a picture / DXF / PDF | (🖼 Obrys) | `drawing_use {as: "sketch"}` (DXF) | partial |
| Extend, construction lines, mirror, offset | (⟷ Prodloužit, ┄ Konstrukční, ⇋ Zrcadlit, ⧈ Odsadit) | — (exact coordinates do it) | gui |
| Snap filters | snap row of the view | — | n/a (the AI gives coordinates) |

## 3D model

| Capability | GUI place | AI tool | Status |
| --- | --- | --- | --- |
| Extrude (up to, other side, draft, a face) | (⬆ Vysunutí) | `add_feature extrude` | ok |
| Revolve, loft, sweep | (⟳ Rotace, ⧫ Šablonování, 〰 Tažení) | `add_feature` | ok |
| Solid from a file | (▣ Těleso ze souboru) | `add_feature {type: "solid", path}` | ok (was gui) |
| Fillet, chamfer (tangent chains) | (◜ Zaoblení, ◸ Zkosení) | `add_feature` + `find_refs` | ok |
| Shell, draft, rib, split | (▢ Skořepina, ⟋ Úkos, ⊿ Žebro, ✂ Rozdělit) | `add_feature` | ok |
| Split pieces as parts | (⧉ Udělat z každého kusu vlastní díl) | — | gui |
| Holes: standards, counterbore / countersink / tapped, fits, D-flat, teardrop, from an axis | (◎ Díra) | `add_feature hole` | ok |
| Text / picture on a face | (Aa Text / obrázek) | `add_feature decal` (text) | partial (no picture) |
| Mirror, pattern, reference point | (⇋ Zrcadlit, ⁂ Pole, • Bod) | `add_feature` | ok |
| Step tree: change, delete, off / on, rename | step row (✎, ✕, ●, 🏷) | `edit_feature`, `delete_feature`, `turn_off_feature` | ok |
| Reorder steps | drag in the tree | — | gui |
| Rollback bar | ⏮ bar | `rollback` | ok |
| Material, tolerances, mass, centre of mass | Part panel | `set_material`, `get_model` | ok |
| Colour, see-through, threads shown | Part panel | `set_look` | ok |
| Paint faces / bodies | (🎨 Obarvit) | `paint_faces` | ok |
| Measure, section, print check | (📏 Měřit, ✂ Řez, 🖨 Kontrola tisku) | `measure`, `set_view {section}`, `check_print` | ok |
| Views, size labels, screenshots | view cube | `set_view`, `get_screenshot` | ok |
| Planes shown, ⊕ centre of mass shown | (◫ Roviny), ⊕ | — | gui (layout) |
| Drawing sheet | (📄 Výkresový list) | `sheet_open` | ok |

## Assembly

| Capability | GUI place | AI tool | Status |
| --- | --- | --- | --- |
| Insert a part | (＋ Vložit díl ▾) | `insert_part` | ok |
| Insert from a file | ＋ Vložit díl ▾ → 📂 | `open_file` then `insert_part` | partial |
| Joints (touch, gap, flush, concentric, angle …), names | (🔗 Vazba) | `snap_faces`, `edit_joint`, `remove_joint` | ok |
| Gears, belts, rack | 🔗 Vazba | `snap_faces {type: gear / belt / rack}` | ok |
| Screw / pin through parts; fasteners at holes | (🔩 Spojovací prvky) | `bolt_parts`, `suggest_fasteners`, `add_fasteners` | ok |
| Place, turn | part panel | `place_part` | ok |
| Fixed in place | (Ukotvený na místě 📌) | `place_part {fixed}` | ok (was gui) |
| One joint is missing | (➕ Přidat vazbu) | `get_assembly` `missing_joint`, `add_missing_joint` | ok (was gui) |
| Free motions: move, limits, lock, name, check | (Pohyb, ⇤⇥, 🔒) | `move_free`, `set_travel`, `lock_motion`, `name_motion`, `check_travel` | ok |
| Mechanism: drive, play, animation | (⚙ Mechanismus, 🎬 Uložit animaci) | `drive_mechanism`, `record_animation` | ok |
| Mechanism trace | ⚙ Mechanismus ⋯ (📈 Průběh) | `drive_mechanism {trace}` | ok (was gui) |
| Mass, centre of mass (whole; each placed part) | panel ⊕ | `get_assembly` `mass_g`, `cog_mm`, parts' `mass_g` | ok (was partial) |
| Collisions | (⚠ Kolize) | `check_collisions` | ok |
| Measure, paint, look, section, explode | (📏 Měřit, 🎨 Obarvit, ✂ Řez, Rozložit) | `measure`, `paint_faces`, `set_look`, `set_view` | ok |
| Explode per part, along joints | 💥, (Podle vazeb) | — | gui (layout) |
| BOM | (Kusovník) | `get_bom`, `export {format: "bom"}` | ok |
| BOM as Excel | Kusovník ⬇ Excel | — (CSV) | partial |
| Make it its own part, edit it here | (⧉ Udělat z něj vlastní díl, ✎ Upravit zde) | `duplicate_part` / `open_part` | partial |
| Simplified look | (Zjednodušeně) | — | gui (layout) |
| Drawing, drawing set PDF | (📄 Výkres) | `sheet_open`, `export {format: "pdf"}` | ok |

## Drawing sheet

| Capability | GUI place | AI tool | Status |
| --- | --- | --- | --- |
| Views, presets, scale, paper, dimensions (add / move / remove / complete / twice), fits | sheet panel | `get_sheet`, `sheet_edit` | ok |
| Title block: texts, templates, styles, frame, logo; BOM page | sheet panel | `sheet_edit` | ok |
| PDF / DXF | Export ▾ | `export` | ok |

## Left to `gui_action` on purpose

Layout and view-only controls (widget docking, opacity, folding, a part's own window, the language, planes / ⊕
shown, explode per part, simplified look) — the AI does not need them; `gui_state` / `gui_action` reach them when a
user asks. Sketch snap filters: the AI gives exact coordinates and never snaps. Tools that need many inputs (split
joints for printing, bending) stay in the GUI (CLAUDE.md: more than ~2 inputs is deferred).
