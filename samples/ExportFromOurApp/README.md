# Files our app exported — open them in other programs

Every file here was **exported by Auto3DModeler itself**, through the same export paths as the Export menu. Open them
in Solid Edge, FreeCAD, a STEP / glTF viewer, a slicer or a DXF viewer, and check that what arrives is right. (Files to
open *in* our app are in `samples/ToImportToOurApp/`.)

Made by `tools/make_export_samples.py`: it builds the models below in headless Edge through the AI's tools and exports
them. To make them again, start a server and run
`PYTHONIOENCODING=utf-8 py tools/make_export_samples.py http://127.0.0.1:<port>`.
`tests/test_export_samples.py` reads every file back and checks the numbers in this table.

## The models

- **Base plate**: 80 × 50 × 10 mm, aluminium, with a Ø10 hole through its centre and **4× M6 threaded countersunk
  holes** (tap drill Ø5 through, countersink Ø12 × 90°) at x ±30, y ±17. Its top face is painted orange (#d9822b).
  Volume **37 864.76 mm³**, mass 102.2 g.
- **Post**: Ø12 × 40 mm, steel, with a blind M5 thread (tap drill Ø4.2, 12 deep) in its top. Volume **4 357.64 mm³**.
- **Post pair** (sub-assembly): the Post twice, 40 mm apart; the second one is green (#2e9e4f) in this assembly.
- **Frame** (assembly): the Base plate (fixed at the origin), **Post pair twice** (on the plate's top at y −8 and +8),
  and **4 library screws ISO 10642 M6×16** in the countersinks (heads flush with the top, 6 mm sticking out below).
  9 bodies, total volume **57 697.89 mm³**, size 80 × 50 × 56 mm (z from −6 to 50).

## The files

| File | What it is | Open it in | What to check |
|---|---|---|---|
| `part_base_plate.step` | The Base plate as a STEP (AP214, mm), one solid, named "Base plate", aluminium grey with its top face orange | Solid Edge, FreeCAD, any STEP viewer | 80 × 50 × 10 mm; the name "Base plate"; the orange top; volume 37 864.76 mm³ (FreeCAD: Part → Check geometry / Mass properties); 15 faces; the 4 countersinks are real cones (Ø12 at the top, 90°); the holes have no modelled thread (only the Ø5 tap drill). |
| `part_base_plate_real_threads.step` | The same plate with **🔩 real threads**: ISO metric M6 grooves cut into the 4 holes (2 MB) | Solid Edge, FreeCAD | One solid; the thread helix visible in the holes (pitch 1 mm); volume about 37 771 mm³ (94 mm³ of grooves less than the plain plate). |
| `part_base_plate.igs` | The same plate as IGES 5.3 (a B-rep solid, mm), named, in its colours | Solid Edge, FreeCAD | It opens as **one solid**, not loose surfaces; same size and volume as the STEP; grey with the orange top. |
| `part_base_plate.stl` | Binary STL (mm) | A slicer (PrusaSlicer, Bambu Studio, Cura), Windows 3D Viewer | 80 × 50 × 10 mm at 100 %; no "repair needed" warning (watertight); round holes in facets. |
| `part_base_plate.obj` | Wavefront OBJ (mm, normals) | Blender, Windows 3D Viewer, MeshLab | Object named `Base_plate`; the same shape as the STL. |
| `part_base_plate.glb` | Binary glTF 2.0 (metres, Y up, PBR material) | gltf-viewer.donmccurdy.com, Blender, Windows 3D Viewer | One node "Base plate"; looks metallic (aluminium) with the orange top; 0.08 × 0.05 × 0.01 m. |
| `part_base_plate.3mf` | 3MF, one object per colour (multi-material printing) | Bambu Studio, PrusaSlicer, Orca Slicer | 80 × 50 × 10 mm; **two colours**: the plate light grey, its top face orange — the slicer offers a filament for each. |
| `assembly_frame.step` | The Frame as a **STEP assembly** (AP214: a product per part, placed instances, sub-assembly nested) | Solid Edge (Open → it builds an .asm), FreeCAD (Assembly / A2plus), a STEP viewer with a tree | The tree **Frame → Base plate-1, Post pair-1, Post pair-2 (each → Post-1, Post-2), 4 screws**; Post is one part used 4×, the screw one part used 4×; Post-2 is green; the plate grey (aluminium) with its orange top, posts and screws steel grey; the screw named "ISO 10642 M6×16"; total volume 57 697.89 mm³. |
| `assembly_frame.igs` | The Frame as **one IGES** (every part placed; IGES has no assembly tree) | Solid Edge, FreeCAD | 9 solids, placed as in the STEP, in their colours (the orange top, the two green posts); each named by its place: "Base plate-1", "Post pair-1/Post-1" … "ISO 10642 M6x16-4" (IGES holds ASCII only: × becomes x); total volume 57 697.89 mm³. |
| `assembly_frame.glb` | The Frame as glTF (a node per placed part, nested; materials) | gltf-viewer.donmccurdy.com, Blender | The node tree as the STEP's (the screws "ISO 10642 M6×16-1" …); the green posts, the orange top; metal look on the steel parts. |
| `assembly_frame.3mf` | The whole Frame as 3MF, an object per colour | A slicer | 80 × 50 × 56 mm; every part where it belongs (each placed part is its own object). |
| `assembly_frame_BOM.csv` | The bill of materials (`;`-separated, decimal comma, UTF-8 — for Excel) | Excel, LibreOffice Calc | 3 rows: Base plate ×1 (aluminium, 102,23 g, made), Post ×4 (steel, 34,21 g, made), ISO 10642 M6×16 ×4 (part number, description, bought). |
| `sheet_base_plate.pdf` | The plate's **drawing sheet**, A4 landscape, scale 1:1 | Any PDF viewer; print it at 100 % ("actual size") | Front / Top / Right views; the callouts **`4× M6 ⌵ Ø12 × 90°`** and **`Ø10 THRU`** (the ⌵ countersink symbol must show, not a box); 80, 50, 10, 60, 34 …; title block: aluminium, 1:1, ISO 2768-m. Printed: the 80 mm edge measures 80 mm with a ruler. |
| `sheet_base_plate.dxf` | The same sheet as DXF (AutoCAD 2010, mm, the paper 1:1) | Solid Edge Draft, AutoCAD, LibreCAD, ShareCAD.org | Layers `visible`, `hidden` (dashed), `dims`, `text`, `frame`; the dimensions are **real DIMENSION entities** that measure 80, 50, 10 …; the countersink callout keeps its ⌵ and ×. |
| `sheet_frame.pdf` | The Frame's assembly drawing, A4, scale 1:2 | A PDF viewer | Front / Top / iso views, balloons 1–3, the parts list (Base plate 1, ◇ Post pair 2, ISO 10642 M6×16 4 with its part number) with each part's material; the title block's material "—". |
| `sheet_frame.dxf` | The assembly drawing as DXF | A DXF viewer | Overall sizes 80, 56, 50 as dimensions; the parts list as text. |
| `project_frame.a3d` | The whole project (💾 Save project; a ZIP: project.json + thumbnail.png): 3 parts, 2 assemblies, 2 sheets | Our app: Open → Project…, or drop it on the window | The tabs Base plate, Post, Post pair, Frame, ISO 10642 M6×16 and the two drawings come back as they were. |

## Export check — what to try

1. **STEP part → Solid Edge / FreeCAD**: `part_base_plate.step`. Measure the volume and the countersink (Ø12, 90°).
   Compare with `part_base_plate.igs`: the same solid. Then `part_base_plate_real_threads.step`: the threads arrive as
   real geometry (a section through a hole shows the thread profile).
2. **STEP assembly → Solid Edge**: open `assembly_frame.step`. You should get an assembly with a sub-assembly "Post
   pair" (used twice) and a part per different part; the names as in the table; the green post.
3. **Slicer**: drop `part_base_plate.stl` and `part_base_plate.3mf` into a slicer: right size, no repair, and the 3MF
   asks for two filaments. `assembly_frame.3mf` shows the whole frame.
4. **glTF viewer**: drop `assembly_frame.glb` on gltf-viewer.donmccurdy.com: the node tree, colours, metal look.
5. **DXF viewer**: open `sheet_base_plate.dxf`, turn layers on / off, click a dimension (it is a real dimension,
   80 mm), check the ⌵ in the callout.
6. **PDF**: print `sheet_base_plate.pdf` at 100 % and measure the 80 mm edge.
7. **BOM**: open `assembly_frame_BOM.csv` in Excel: columns split at `;`, numbers with a decimal comma, "×" readable.

## Known faults

None known (2026-10-28: the "×" in names, the part STEP's name and colours, the painted face outside 3MF, the IGES
names, the assembly sheet's "PLA" and the BOM's "made (3D print)" for metal parts are fixed; tests/test_export_samples.py
checks each). Still as designed: IGES names are ASCII ("M6x16"); a face painted on one placed part in an assembly (not in
its part) is in the 3MF only.
