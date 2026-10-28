# Files to import into our app

Real files made by other programs — CAD parts and assemblies (STEP, IGES), meshes, drawings, a PDF drawing,
pictures and a PCB — with a clear licence each. Open them in the app as the table says and compare with what you
should see. The tests open them too: `tests/test_cad_samples.py` (every STEP / IGES under 3 MB; `A3D_SLOW_SAMPLES=1`
for all) and `tools/e2e_cad_samples.py` (every file, in the browser). `samples.json` holds the same list with the
values the kernel measured when the files were added.

Total: 54.6 MB. **`solidedge/`** is for the owner's own Solid Edge exports (STEP / IGES / DXF) — empty for now.

"Made by" is read from each file (the STEP header's originating system, the IGES global section, the DXF / DWG
version, the STL / OBJ / Gerber comments). NIST blanked it in its PMI test files: for those, the program in [brackets]
is a guess from how the file is written (CATIA: 'PartBody' / 'Closed Shell'; Creo: '05___PRT_ALL_…' layers; NX:
numbered layers).

## CAD parts and assemblies (STEP, IGES)

| file | made by | format | how to open it in our app | what you should see |
|---|---|---|---|---|
| `nist/nist_ctc_01_asme1_rd.stp` | [NX — header blanked by NIST; NX layer numbers] | AP203 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | first the question “Open as an assembly?” (the file holds extra shapes) → *Open as one body* → a 3D model: 139 faces, 14,642.8 cm³, 1170 × 650 × 150 mm |
| `nist/nist_ctc_04_asme1_rd.stp` | [CATIA V5 — header blanked by NIST; 'PartBody', 'Closed Shell'] | AP203 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | first the question “Open as an assembly?” (the file holds extra shapes) → *Open as one body* → a 3D model: 518 faces, 17,518.6 cm³, 500 × 780 × 131 mm |
| `nist/nist_ctc_05_asme1_rd.stp` | [Creo — header blanked by NIST; '05___PRT_ALL_DTM_CSYS' layers] | AP203 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | first the question “Open as an assembly?” (the file holds extra shapes) → *Open as one body* → a 3D model: 209 faces, 12,829.0 cm³, 527 × 559 × 483 mm |
| `nist/nist_ftc_07_asme1_rd.stp` | [unknown — header blanked by NIST] | AP203 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 269 faces, 1,726.2 cm³, 312 × 136 × 223 mm; a fillet on any of the 8 longest edges of its 4 biggest faces is refused: 'These edges cannot be rounded here (whatever the size)' |
| `nist/nist_ctc_02_asme1_ap242-e2.stp` | [CATIA V5 — header blanked by NIST; 'PartBody', face ids] | AP242 e2 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | first the question “Open as an assembly?” (the file holds extra shapes) → *Open as one body* → a 3D model: 637 faces, 45,468.7 cm³, 680 × 860 × 400 mm; the volume counts 2 loose faces: 45.47 instead of 47.11 · 10⁶ mm³; a cut / hole then raises it; ⚠ *Open as an assembly* fails (the server's kernel crashes on this file — a known bug) |
| `nist/nist_ftc_10_asme1_ap242-e2.stp` | [unknown — header blanked by NIST] | AP242 e2 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | first the question “Open as an assembly?” (the file holds extra shapes) → *Open as one body* → a 3D model: 282 faces, 188.2 cm³, 158 × 31 × 75 mm |
| `nist/nist_stc_06_asme1_ap242-e3.stp` | [unknown — header blanked by NIST] | AP242 e3 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 144 faces, 3,323.5 cm³, 248 × 305 × 128 mm |
| `nist/nist_ftc_08_asme1_ap242-e1-tg.stp` | [unknown — header blanked by NIST] | AP242 e1 tessellated | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | first the question “Open as an assembly?” (the file holds extra shapes) → *Open as one body* → a 3D model: 273 faces, -313.1 cm³, no size; tessellated (faceted) geometry: a body with a negative volume and no box; its sheet never builds, IGES / GLB fail |
| `nist/827-9999-906.stp` | SIEMENS PLM Software NX 8.5 (ST-DEVELOPER v15) | AP203 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 89 faces, 22.9 cm³, 103 × 70 × 20 mm |
| `nist/827-9999-904 rev c.stp` | 3D_Evolution (CT CoreTechnologie) from NX | AP242 e1 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 117 faces, 22.9 cm³, 103 × 70 × 20 mm |
| `freecad-library/Pico-R3.step` | SolidWorks 2021 (SwSTEP 2.0) | AP203 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 12 different parts placed 13 times, 1 sub-assemblies, 21 × 4 × 52 mm |
| `freecad-library/PM-16-50-CYLINDER.STEP` | SolidWorks 2010 (SwSTEP 2.0) | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 4 different parts placed 4 times, 0 sub-assemblies, 159 × 18 × 19 mm |
| `freecad-library/VALVULA 5-2 VIAS PNEUMATICA SIMPLES SOLENOIDE.STEP` | SolidWorks 2017 (SwSTEP 2.0) | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 12 different parts placed 24 times, 0 sub-assemblies, 357 × 138 × 168 mm |
| `freecad-library/VALVULA 5-2 VIAS PNEUMATICA SIMPLES SOLENOIDE.IGS` | SolidWorks 2017 | IGES 5.3 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a see-through 👁 reference body and a warning that its surfaces do not close (no solid to edit); 1995 faces, 357 × 138 × 168 mm |
| `freecad-library/MIT E Vent Pre Production Model.step` | Autodesk Translation Framework v8.12 (Fusion 360 / Inventor; ST-DEVELOPER v18) | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 13 different parts placed 41 times, 0 sub-assemblies, 271 × 241 × 381 mm; the assembly sheet takes over the kernel worker's 120 s: 500, no message |
| `freecad-library/Reespirator23 v7.step` | Autodesk Translation Framework v8.12 (Fusion 360 / Inventor; ST-DEVELOPER v18) | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 13 different parts placed 26 times, 1 sub-assemblies, 329 × 183 × 291 mm; a Ø3 × 1 cut and a Ø2 hole on its biggest part (balloon: one B-spline solid of 8 faces) raise the volume by ~4 000 / 3 200 mm³ |
| `freecad-library/Ayar saci 180.stp` | ACIS (Bosch Rexroth catalogue via CADClick) | AP203 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 175 faces, 31.7 cm³, 130 × 30 × 95 mm |
| `freecad-library/MK8.iges` | Open CASCADE 6.8 (FreeCAD) | IGES 5.3 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a 3D model; a note that its surfaces were sewn into a solid; 665 faces, 80 × 52 × 74 mm |
| `freecad/as1-ac-214.stp` | AutoCAD 2000 (AutoCAD STEP 2000) — CAx-IF AS1 | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 5 different parts placed 18 times, 3 sub-assemblies, 200 × 150 × 87 mm |
| `freecad/Schenkel.stp` | CATIA V5 R14 (CATIA V5 STEP AP203) | AP203 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 409 faces, 121.1 cm³, 155 × 155 × 20 mm |
| `occt/screw.step` | EUCLID (Matra Datavision) OL-2.0B | AP214 CC1 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 10 faces, 3.8 cm³, 20 × 20 × 42 mm |
| `occt/linkrods.step` | EUCLID (Matra Datavision) OL-2.0B | AP214 CC1 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 37 faces, 0.0 cm³, 5 × 2 × 2 mm |
| `occt/bearing.iges` | EUCLID-QUANTUM (Matra Datavision) OL-2.0B | IGES | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a see-through 👁 reference body and a warning that its surfaces do not close (no solid to edit); 213 faces, 0 × 0 × 0 mm |
| `occt/hammer.iges` | EUCLID-QUANTUM (Matra Datavision) OL-1.5A | IGES | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a see-through 👁 reference body and a warning that its surfaces do not close (no solid to edit); 45 faces, 13179 × 4290 × 38431 mm |
| `stepcode/as1-oc-214.stp` | Open CASCADE 6.1 (Datakit converter) — CAx-IF AS1 | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 5 different parts placed 18 times, 3 sub-assemblies, 200 × 150 × 84 mm |
| `stepcode/dm1-id-214.stp` | I-DEAS Master Series 9 (SDRC) — CAx-IF DM1 | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 3 different parts placed 7 times, 0 sub-assemblies, 50 × 87 × 100 mm; every face is a B-spline (flat ones too): no face counts as flat, so no sketch / hole on it |
| `stepcode/io1-cm-214.stp` | CoCreate Modeling 16.00 (PTC) — CAx-IF IO1 | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 29 faces, 78.2 cm³, 31 × 88 × 88 mm |
| `stepcode/sg1-c5-214.stp` | CATIA V5 R20 (CATIA V5 STEP AP214) — CAx-IF SG1 | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 16 faces, 355.9 cm³, 80 × 80 × 154 mm |
| `stepcode/s1-c5-214/s1-c5-214.stp` | CATIA V5 R19 (CATIA V5 STEP AP214) — CAx-IF S1, external references to 12 part files | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | an error message: “The file has no solid in it.” |
| `occt-import-js/as1_pe_203.stp` | PRO/ENGINEER 2008340 (PTC) — CAx-IF AS1 (declares INCH: 25.4× the others) | AP203 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 5 different parts placed 18 times, 8 sub-assemblies, 5080 × 2210 × 3810 mm |
| `occt-import-js/dm1-pe-214.stp` | PRO/ENGINEER 2008490 (PTC) — CAx-IF DM1 | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 3 different parts placed 7 times, 1 sub-assemblies, 2540 × 2210 × 1270 mm |
| `occt-import-js/as1-tu-203.stp` | UG (Unigraphics / NX) via Theorem Solutions GCO -> AP203 E2 10.0 — CAx-IF AS1 | AP203 e2 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as an assembly** | the question “Open as an assembly?” → an assembly of 5 different parts placed 18 times, 3 sub-assemblies, 200 × 150 × 84 mm |
| `occt-import-js/io1-tu-203.stp` | UG (Unigraphics / NX) via Theorem Solutions — CAx-IF IO1 | AP203 e2 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | first the question “Open as an assembly?” (the file holds extra shapes) → *Open as one body* → a 3D model: 29 faces, 78.2 cm³, 31 × 88 × 88 mm |
| `occt-import-js/Cube 10x10.stp` | Autodesk Inventor 2019 (ST-DEVELOPER v17) | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 6 faces, 1.0 cm³, 10 × 10 × 10 mm |
| `occt-import-js/Cube 10x10.igs` | Autodesk Inventor 2019 | IGES | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a 3D model with the exact solid; 6 faces, 10 × 10 × 10 mm |
| `occt-import-js/conical-surface.step` | Autodesk Translation Framework v13.14 (Fusion 360; ST-DEVELOPER v20) | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 5 faces, 2.5 cm³, 7 × 27 × 27 mm |
| `occt-import-js/cube-in.step` | FreeCAD (Open CASCADE 7.6), in INCH: a 1 m cube | AP214 | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), then **Open as one body** when asked | a 3D model: 6 faces, 1,000,000.0 cm³, 1000 × 1000 × 1000 mm |

## Other formats

| file | made by | format | how to open it in our app | what you should see |
|---|---|---|---|---|
| `mesh/Nema-17_MountBracket.stl` | FreeCAD (Open CASCADE STL writer) | STL (binary) | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a quick part (the mesh, sliced for printing) |
| `mesh/608ZZ_Ball_Bearing.stl` | FreeCAD (Open CASCADE STL writer) | STL (binary) | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a quick part (the mesh, sliced for printing) |
| `mesh/rj11.obj` | FreeCAD | OBJ | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a quick part (the mesh, sliced for printing) |
| `mesh/box.3mf` | 3MF Consortium sample | 3MF | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a quick part (the mesh, sliced for printing): a 10 × 20 × 30 mm box |
| `mesh/cube_gears.3mf` | 3MF Consortium sample | 3MF | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a quick part (the mesh, sliced for printing): the cube and its 16 gears (17 objects) placed as in the file, 168 × 125 × 34 mm |
| `drawings/Drive Gear.dxf` | unknown (MIT E-Vent laser-cut parts) | DXF R14 (AC1014) | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a 📐 2D drawing: 307 shapes on 1 layers — measure, tidy up, *Use ▾* as a sketch or a quick part |
| `drawings/Finger.dxf` | unknown (MIT E-Vent laser-cut parts) | DXF R14 (AC1014) | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | a 📐 2D drawing: 228 shapes on 1 layers — measure, tidy up, *Use ▾* as a sketch or a quick part |
| `drawings/surgical_mask_strap.dwg` | unknown (AutoCAD R14 format) | DWG R14 (AC1014) | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view) | nothing opens — DWG needs the free ODA File Converter or LibreDWG on the computer (not installed here): the app says so |
| `pdf/nist_ftc_11_asme1_rb.pdf` | NIST FTC-11 drawing (from the CAD model) | PDF drawing | 📂 Open ▾ → *PDF drawing…* | nothing opens — read, but no part: Checks says No closed outline found in the drawing (a GD&T sheet with many views) |
| `pdf/nist_ctc_01_asme1_rd.pdf` | NIST CTC-01 drawing (from the CAD model) | PDF drawing | 📂 Open ▾ → *PDF drawing…* | a quick part made from the drawing's views and dimensions (check the Checks list); box [0, 0, 25, 9] mm — but not the real part: a 25 × 9 mm outline with “1 error and 81 warnings” (the part is 1170 × 650 mm — the GD&T sheet is beyond the PDF reader) |
| `pictures/Hex-nut.png` | a drawn picture (Wikimedia Commons) | PNG | 📂 Open ▾ → *Picture — trace an outline…* | the outline wizard with the part's outline found (1 candidates); *Use* → a quick part |
| `pictures/Bolt_Nut_and_Washer_MET_126417.jpg` | a photo (The Metropolitan Museum of Art, Open Access) | JPG | 📂 Open ▾ → *Picture — trace an outline…* | the outline wizard with the part's outline found (5 candidates); *Use* → a quick part |
| `pcb/olimex-esp32-evb-revC` | KiCad Pcbnew (2017) | Gerber X2 + Excellon (11 files) | 📂 Open ▾ → *CAD / PCB / 3D file…* (or drop it on the 3D view), pick **all 11 files** together | a 📐 board drawing: copper, outline, holes — 23111 shapes on 11 layers |

## Sources and licences

| file | licence | source |
|---|---|---|
| `nist/nist_ctc_01_asme1_rd.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `nist/nist_ctc_04_asme1_rd.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `nist/nist_ctc_05_asme1_rd.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `nist/nist_ftc_07_asme1_rd.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `nist/nist_ctc_02_asme1_ap242-e2.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `nist/nist_ftc_10_asme1_ap242-e2.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `nist/nist_stc_06_asme1_ap242-e3.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `nist/nist_ftc_08_asme1_ap242-e1-tg.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `nist/827-9999-906.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-d2mi-modelszip> |
| `nist/827-9999-904 rev c.stp` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-d2mi-modelszip> |
| `freecad-library/Pico-R3.step` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Computing/SingleBoardComputers/Raspberry/Raspberry%20Pi%20Pico/Pico-R3.step> |
| `freecad-library/PM-16-50-CYLINDER.STEP` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Electro-pneumatic/Cylinders/PM-16-50-CYLINDER.STEP> |
| `freecad-library/VALVULA 5-2 VIAS PNEUMATICA SIMPLES SOLENOIDE.STEP` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Electro-pneumatic/Manifolds/FESTO/VALVULA%205-2%20VIAS%20PNEUMATICA%20SIMPLES%20SOLENOIDE.STEP> |
| `freecad-library/VALVULA 5-2 VIAS PNEUMATICA SIMPLES SOLENOIDE.IGS` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Electro-pneumatic/Manifolds/FESTO/VALVULA%205-2%20VIAS%20PNEUMATICA%20SIMPLES%20SOLENOIDE.IGS> |
| `freecad-library/MIT E Vent Pre Production Model.step` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Medical%20Parts/01%20Biomedical/MIT%20E%20Vent/MIT%20E%20Vent%20Pre%20Production%20Model.step> |
| `freecad-library/Reespirator23 v7.step` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Medical%20Parts/01%20Biomedical/Respirador%20ResistenciaTeam/Reespirator23%20v7.step> |
| `freecad-library/Ayar saci 180.stp` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Mechanical%20Parts/Profiles%20EN/Sigma%20profiles/Ayar%20saci%20180.stp> |
| `freecad-library/MK8.iges` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Electrical%20Parts/Hotend/MK8.iges> |
| `freecad/as1-ac-214.stp` | LGPL-2.1 (FreeCAD test data) | <https://github.com/FreeCAD/FreeCAD/blob/main/data/tests/Step/as1-ac-214.stp> |
| `freecad/Schenkel.stp` | LGPL-2.1 (FreeCAD example data) | <https://github.com/FreeCAD/FreeCAD/blob/main/data/examples/Schenkel.stp> |
| `occt/screw.step` | LGPL-2.1 with OCCT exception (OCCT sample data) | <https://github.com/Open-Cascade-SAS/OCCT/blob/master/data/step/screw.step> |
| `occt/linkrods.step` | LGPL-2.1 with OCCT exception (OCCT sample data) | <https://github.com/Open-Cascade-SAS/OCCT/blob/master/data/step/linkrods.step> |
| `occt/bearing.iges` | LGPL-2.1 with OCCT exception (OCCT sample data) | <https://github.com/Open-Cascade-SAS/OCCT/blob/master/data/iges/bearing.iges> |
| `occt/hammer.iges` | LGPL-2.1 with OCCT exception (OCCT sample data) | <https://github.com/Open-Cascade-SAS/OCCT/blob/master/data/iges/hammer.iges> |
| `stepcode/as1-oc-214.stp` | BSD-3-Clause (STEPcode collective work; CAx-IF test file) | <https://github.com/stepcode/stepcode/blob/develop/data/ap214e3/as1-oc-214.stp> |
| `stepcode/dm1-id-214.stp` | BSD-3-Clause (STEPcode collective work; CAx-IF test file) | <https://github.com/stepcode/stepcode/blob/develop/data/ap214e3/dm1-id-214.stp> |
| `stepcode/io1-cm-214.stp` | BSD-3-Clause (STEPcode collective work; CAx-IF test file) | <https://github.com/stepcode/stepcode/blob/develop/data/ap214e3/io1-cm-214.stp> |
| `stepcode/sg1-c5-214.stp` | BSD-3-Clause (STEPcode collective work; CAx-IF test file) | <https://github.com/stepcode/stepcode/blob/develop/data/ap214e3/sg1-c5-214.stp> |
| `stepcode/s1-c5-214/s1-c5-214.stp` | BSD-3-Clause (STEPcode collective work; CAx-IF test file) | <https://github.com/stepcode/stepcode/tree/develop/data/ap214e3/s1-c5-214> |
| `occt-import-js/as1_pe_203.stp` | LGPL-2.1 (occt-import-js test data) | <https://github.com/kovacsv/occt-import-js/blob/main/test/testfiles/cax-if/as1_pe_203.stp> |
| `occt-import-js/dm1-pe-214.stp` | LGPL-2.1 (occt-import-js test data) | <https://github.com/kovacsv/occt-import-js/blob/main/test/testfiles/cax-if/dm1-pe-214.stp> |
| `occt-import-js/as1-tu-203.stp` | LGPL-2.1 (occt-import-js test data) | <https://github.com/kovacsv/occt-import-js/blob/main/test/testfiles/cax-if/as1-tu-203.stp> |
| `occt-import-js/io1-tu-203.stp` | LGPL-2.1 (occt-import-js test data) | <https://github.com/kovacsv/occt-import-js/blob/main/test/testfiles/cax-if/io1-tu-203.stp> |
| `occt-import-js/Cube 10x10.stp` | LGPL-2.1 (occt-import-js test data) | <https://github.com/kovacsv/occt-import-js/blob/main/test/testfiles/cube-10x10mm/Cube%2010x10.stp> |
| `occt-import-js/Cube 10x10.igs` | LGPL-2.1 (occt-import-js test data) | <https://github.com/kovacsv/occt-import-js/blob/main/test/testfiles/cube-10x10mm/Cube%2010x10.igs> |
| `occt-import-js/conical-surface.step` | LGPL-2.1 (occt-import-js test data) | <https://github.com/kovacsv/occt-import-js/blob/main/test/testfiles/conical-surface/conical-surface.step> |
| `occt-import-js/cube-in.step` | LGPL-2.1 (occt-import-js test data) | <https://github.com/kovacsv/occt-import-js/blob/main/test/testfiles/cube-units/cube-in.step> |
| `mesh/Nema-17_MountBracket.stl` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Electrical%20Parts/Motors/Stepper/NEMA/Nema-17_Mount_Bracket/Nema-17_MountBracket.stl> |
| `mesh/608ZZ_Ball_Bearing.stl` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Mechanical%20Parts/Bearings/608ZZ_Ball_Bearing.stl> |
| `mesh/rj11.obj` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Electronics%20Parts/Connectors/Telephone%20connectors/rj11.obj> |
| `mesh/box.3mf` | BSD-2-Clause (3MF Consortium samples) | <https://github.com/3MFConsortium/3mf-samples/blob/master/examples/core/box.3mf> |
| `mesh/cube_gears.3mf` | BSD-2-Clause (3MF Consortium samples) | <https://github.com/3MFConsortium/3mf-samples/blob/master/examples/core/cube_gears.3mf> |
| `drawings/Drive Gear.dxf` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Medical%20Parts/01%20Biomedical/MIT%20E%20Vent/DXFs%20For%20Website/Drive%20Gear.dxf> |
| `drawings/Finger.dxf` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Medical%20Parts/01%20Biomedical/MIT%20E%20Vent/DXFs%20For%20Website/Finger.dxf> |
| `drawings/surgical_mask_strap.dwg` | CC-BY 3.0 (FreeCAD-library: 'All Parts in this repository are licensed under CC-BY 3.0') | <https://github.com/FreeCAD/FreeCAD-library/blob/master/Medical%20Parts/Surgical%20mask%20strap/files/surgical_mask_strap.dwg> |
| `pdf/nist_ftc_11_asme1_rb.pdf` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `pdf/nist_ctc_01_asme1_rd.pdf` | public domain (US government work, 17 USC 105; NIST: 'can be used without any restrictions') | <https://www.nist.gov/document/nist-pmi-step-files> |
| `pictures/Hex-nut.png` | public domain (Wikimedia Commons) | <https://commons.wikimedia.org/wiki/File:Hex-nut.png> |
| `pictures/Bolt_Nut_and_Washer_MET_126417.jpg` | CC0 (The Met Open Access) | <https://commons.wikimedia.org/wiki/File:Bolt,_Nut,_and_Washer_MET_126417.jpg> |
| `pcb/olimex-esp32-evb-revC` | Apache-2.0 (OLIMEX ESP32-EVB) | <https://github.com/OLIMEX/ESP32-EVB/tree/master/HARDWARE/REV-C/Gerbers> |

- `nist/`, `pdf/`: the NIST MBE PMI test models (https://www.nist.gov/document/nist-pmi-step-files) and the D2MI models
  (https://www.nist.gov/document/nist-d2mi-modelszip): works of the US government, not subject to copyright (17 USC 105);
  NIST: "The test cases, CAD models, and STEP files can be used without any restrictions." Acknowledgement as NIST asks:
  *from the NIST MBE PMI Validation and Conformance Testing Project and the NIST D2MI project*. No NIST endorsement implied.
- `freecad-library/`, `mesh/` (STL, OBJ), `drawings/`: https://github.com/FreeCAD/FreeCAD-library — "All Parts in this
  repository are licensed under CC-BY 3.0. Each Part is copyrighted by and should be attributed to its respective
  author(s)" (the repository's history names each file's author). Unchanged.
- `freecad/`: FreeCAD's test / example data (LGPL-2.1). `occt/`: Open CASCADE's sample data (LGPL-2.1 with the OCCT
  exception). `occt-import-js/`: test data of kovacsv/occt-import-js (LGPL-2.1). `stepcode/`: CAx-IF round-robin files
  shipped in STEPcode (BSD-3-Clause collective work).
- `mesh/*.3mf`: 3MF Consortium samples (BSD-2-Clause). `pcb/`: OLIMEX ESP32-EVB Rev C Gerbers (Apache-2.0).
  `pictures/`: Wikimedia Commons — Hex-nut.png (public domain), Bolt, Nut, and Washer (The Met, CC0).

Downloaded as data only: nothing in them is run. Not taken: files behind a login (GrabCAD, TraceParts), files with no
licence or a non-commercial one (a Solid Edge camera project under CC BY-NC-SA), vendor component models copied into
electronics repositories (their own licence unclear).
