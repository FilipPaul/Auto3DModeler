# j-separse: can we read Solid Edge .par / .asm files ourselves?

Feasibility probe, 2026-10-30. Input was a read-only copy of 12 .par files, 1 .asm and Krytka 2.stl, from Solid Edge 2025 (Parasolid 36.0.208 and 37.0.192).
Solid Edge was **not** started. No COM was used. Nothing in the repo or the owner's folder was changed.
The owner's STEP export ("Sestava zakladani.stp") had **not** appeared in `Documents\Zakládání` when the probe ended, so nothing was compared against STEP.

All paths below are relative to the scratchpad
`C:\Users\PAULSW~1\AppData\Local\Temp\claude\c--DEVELOPMENT-PROJECTS-Auto3DModeler\3e4ff66a-f7ae-4870-b740-71d73e7a0231\scratchpad\`.

## 1. The OLE container
Both file types are plain OLE2 compound files, and `olefile` reads them without trouble. The full listing with sizes and first bytes is in `j-separse-out/j-separse-streams.txt`, made by `j-separse-list.py`.

**.par** (Pin_DIN_7_1981_3m6x10.par, 45 streams). The streams that matter:

| Stream | Size | What it is |
|---|---|---|
| `PARASOLID/STREAM0.P_B` | 4 610 | **Parasolid partition, binary, uncompressed** (`GUISE=transmit_partition`, `FORMAT=binary`) |
| `PARASOLID/STREAM0.D_B` | 2 352 | Parasolid partition **deltas** (roll-back marks), not needed for the current state |
| `PARASOLID/STREAM0S2.P_B / .D_B` | 3 905 / 4 075 | A second partition (the "Simplify" body: the pin with plain flat ends) |
| `PARASOLID/SKETCH.P_B` (some parts) | up to 200 k | The sketch geometry as a Parasolid general body (wire edges) |
| `PSMcluster0` | 86 041 | Solid Edge's own object store (persistent C++ objects): features, dimensions, expressions |
| `PSMtypetable` | 6 963 | The class table for that store: "Part Dimensions Owner PARTDEX", "Double Value Object EXPRDEX", "JDimParameters Object ANNOT", … |
| `PSMroots`, `PSMclustertable`, `PSMsegmenttable`, `PSMspacemap/*` | small | Indexes for the PSM store |
| `Display/Cache*` | 5–28 k | Nested OLE files holding the tessellated display |
| `Display/Styles/Library0` | 3 k | zlib-compressed (`78 9c`) style library |
| `PartsLiteData`, `GeometricVersionHistory`, `\x05SummaryInformation`, … | small | Metadata |

**.asm** (Sestava zakladani.asm, 1.18 MB): `Attachments` (77 k), `JAsmRefAttr` (41 k), `IOT/Default`, `JSite<N>/\x01Ole` (one per referenced file, 8 in all), `Preview/Structure/{IDS,IOT,Sites}`, `Preview/Display/Scene0/Geometries` (a 472 k nested OLE file holding the display meshes), and the same PSM* object store (312 k). The `PARASOLID` storage is empty, so the assembly holds no exact part geometry.

## 2. Geometry: Parasolid XT inside the .par
- `PARASOLID/STREAM0.P_B` is a standard **Parasolid binary transmit file** in the neutral "PS" encoding, partition guise. It has the usual `**ABCDEFGH…` text header, then `PS\0\0\0` + `: TRANSMIT FILE (partition) created by modeller version 3600208`, then the schema key `SCH_3600208_36001_13006`. That key means: base schema 13006 plus an **embedded schema delta** to v36.
- The stream is **not compressed**. Copied out as it is, it is a valid `.x_b` file. All 38 Parasolid streams are extracted to `j-separse-out/xt/j-separse-<part>__<stream>`.
- **Existing reader:** [parasolid-kit](https://github.com/monozukuri-ai/parasolid-kit) ([PyPI](https://pypi.org/project/parasolid-kit/), v0.3.8, Oct 2026, MIT/Apache-2.0, Rust core). It is young and marked experimental, but it reads both binary and text XT and maps the result to a typed B-rep.
  - It needs the **base schema catalog** `sch_13006.sch_txt`. Siemens does not let it bundle that file.
  - The Solid Edge 2025 install has the catalog at `C:\Program Files\Siemens\Solid Edge 2025\Schema\` (183 files). The probe copied it to `j-separse-schema/` for testing only. It must not be redistributed.
  - A trick works without the catalog: renaming the key to the built-in SolidWorks profile `SCH_3101290_31100_13006` parses 9 of 20 partitions. The other 11 fail on attribute node types 87 / 91.
- **Result with the real 13006 catalog: 20 of 20 partitions parse, 19 completely, with valid topology.**
  - Surface types seen: plane, cylinder, cone, sphere, torus.
  - Curve types seen: line, circle, ellipse, intersection, NURBS.
  - The one incomplete partition is the base plate (541 faces): 13 `SWEPT_SURF` faces are not mapped.
- **parasolid-kit's own OCCT export** failed on every part. It refuses trimmed spheres and vertex-trimmed circles, and its `[occt]` extra needs OCP < 7.10, while the app has OCP 8.0.1.
- **So I wrote a 250-line converter** (`j-separse-xt2occ.py`). It turns the parsed B-rep into OCCT, using OCP 8 through `j-separse-venv2`, and builds faces from surface + loops, then sews them.

| Part | Faces built / source | Valid | Volume (mm³) | Check |
|---|---|---|---|---|
| **Krytka** | 19 / 19 | yes | **3 710.920** | **STL export from Solid Edge: 3 710.918 mm³; bbox 41×15×7 mm in both, exact** |
| U-165 eccentric pin | 14 / 14 | yes | 1 427.44 | vertices lie on their surfaces to 5e-15 mm |
| U-157 pad | 6 / 6 | yes | 65.71 | bbox 4×7.5×4 mm |
| U-096 thread insert | 7 / 7 | yes | 87.60 | bbox Ø6.3×5 mm |
| Pin 3m6×10 | 3 / 4 | yes, but wrong | 124 (expected about 71) | A closed edge on a sphere picks the wrong cap; the 4th face is a construction sheet |
| Screw DIN 7991 M3 | 24 / 30 | no | – | Faces bounded by intersection curves fail; the probe only fits them crudely |
| Zakladaci deska | – | – | – | NURBS pole/degree handling bug in the probe, and `SWEPT_SURF` is not mapped |

The STEP files written are in `j-separse-out/step/j-separse-*.step`. Units are metres in XT and are converted ×1000 to mm. The part's geometry coordinates read directly as millimetre values: pin radius 1.5, sphere ends R3, plate 311×246×5.

## 3. Assembly (.asm): occurrences and placements decoded
- **Referenced files:** there are 8 unique .par files. Their full UNC paths (`\\nas1\RAFIONTECH\…\Zakládání\*.par`) are stored as UTF-16 strings in `Attachments`, `JAsmRefAttr`, `JSite*/\x01Ole` (one OLE link site per file) and `Preview/Structure/Sites`.
- **Occurrences:** `Preview/Structure/IDS` has **209** occurrence names, `name.par:N` in UTF-16:
  - 173 × U-157 pad;
  - 11 × screw DIN 7991 M4×12;
  - 10 × eccentric pin;
  - 10 × thread insert;
  - 2 × pin 4m6×10;
  - 1 × ISO 1207 screw;
  - 1 × Krytka;
  - 1 × base plate.
- **Placements:** that stream also holds **209 4×4 float64 matrices**, column-major, little-endian, in metres. Each one sits 132 bytes before its occurrence name. `Attachments` holds another 209. The decoded list is in `j-separse-out/j-separse-asm-placements.json` (made by `j-separse-asm3.py`).
- **Sanity check: every placement makes physical sense.**
  - The plate sits at the origin with identity rotation. Its own bbox is 0–311 × 0–246 × 0–5 mm.
  - All 10 eccentric pins sit on the top face (z = 5).
  - All 10 inserts sit at z = 0 and are flipped (R₃₃ = −1), so they go in from below at the same XY as the pins, e.g. (52, 8.7).
  - All 11 countersunk screws sit at z = 3.
  - All 173 pads sit at z = 7.5, rotated 90° about X.
  - All XY values fall inside the plate (0–305 × 0–238).
  - Rotations are exactly orthonormal.
- **Open questions:**
  - `Preview/Structure` is a "lightweight preview" structure. It is easy to read, but it might be stale if the file was saved without a refresh.
  - The `Attachments` matrices are the authoritative ones. They use a different order and some different z values, which looks like relative or constraint-frame data, so that stream needs a controlled sample to pin down.
  - Sub-assemblies, suppressed or hidden occurrences, and mates are not decoded.

## 4. Sketches, dimensions, features
- **Sketch geometry is easy.** `PARASOLID/SKETCH.P_B` is a Parasolid general body of wire edges, and it parses completely. The base plate's sketch has 416 circles and 16 lines; U-165's has 3 circles and 2 lines. That gives the curves, but no constraints or dimension objects.
- **Feature history and dimensions are hard.** They live in `PSMcluster0`, Solid Edge's proprietary persistent-object store, whose class table (`PSMtypetable`, 238 entries) lists Solid Edge internals. In the pin, the store contains the strings "Protrusion" ×4, "Revolve" ×5, "Profile" ×9, "Dimension" ×3, "Length" ×3. The dimension values appear as little-endian doubles in metres: 0.003 ×24, 0.01 ×4, 0.0015 ×6.
- So values can be **found**, but tying them to a feature, sketch entity or variable means reverse-engineering an undocumented C++ serialization with about 240 classes, many per add-in. It changes with every Solid Edge release.

## 5. Legal flag (not legal advice)
- The **EU Software Directive 2009/24/EC, art. 6** (Czech law: autorský zákon §66(1)(f)) allows decompiling and reverse engineering only where that is indispensable for interoperability, by a lawful user, limited to the parts needed. Contract terms that override art. 6 are void (art. 8).
- Reading a **file format** the user created is weaker ground than decompiling and is generally lower risk. The Siemens EULA, however, forbids reverse engineering of the *software*.
- The safe line:
  - read files only, never disassemble Solid Edge or Parasolid binaries;
  - never redistribute Siemens schema files: the user points the app at their own `Schema\sch_13006.sch_txt`, or we derive our own field list from the public "Parasolid XT Format Reference", which documents the node schema;
  - using Solid Edge itself through COM to make samples for format study is "observing the program's behaviour", which art. 5(3) allows a licensee.
- Ask a lawyer before shipping a product feature that does this.

## Verdict

| | Feasible? | Effort | Risks |
|---|---|---|---|
| **(a) Assembly structure and placements** | **Yes. Largely decoded already** (209 / 209 occurrences, sane transforms) | **3–5 days** for a robust reader: use the `Attachments` / `JAsmRefAttr` data rather than the Preview, handle sub-assemblies, suppressed and hidden occurrences, and test against a STEP of the assembly | Preview data may be stale; layouts differ between versions; mates and constraints are not covered |
| **(b) Exact B-rep through Parasolid XT** | **Yes for analytic parts. Proven exact on Krytka** (volume matches the STL to 0.002 mm³) | **2–4 weeks** to reach about 95 % of real parts. That means: (1) the probe's open bugs: closed edges on spheres, NURBS handling, face sense; (2) intersection curves done properly, by intersecting the two surfaces in OCCT instead of fitting chart points; (3) mapping `SWEPT_SURF`, `SPUN_SURF`, `OFFSET_SURF` and blend surfaces; (4) tests against STEP exports. parasolid-kit does the parsing, about 1 day to integrate. | Depends on a young third-party library; the schema catalog comes from the user's Siemens install and cannot be shipped; blends, offsets and swept faces are the long tail; newer Parasolid versions change the schema |
| **(c) Sketches, dimensions, features** | **Sketch curves: yes** (days). **Feature history and parametric dimensions: no**, not reliably | Sketch wires: about 2 days. Features and dimensions from `PSMcluster0`: months, open-ended, and broken by each Solid Edge release | Undocumented proprietary object store; legally the weakest part; low payoff, since the B-rep plus the assembly gives a "dumb" but exact model |
| **(d) Writing native .par / .asm** | **No** | Not realistic without Solid Edge: a .par needs a consistent PSM store with feature tree, styles and views, which Solid Edge validates. The way out is to **export STEP / Parasolid .x_t**, which Solid Edge imports natively. parasolid-kit can write .x_b, but only by round-tripping an existing document. | Corrupted files, and support issues for users |

## Recommended next step
1. **Asm-reader slice, about 1 week.** Build a "Solid Edge import (beta)". For each part, read the `.asm` occurrences and placements, plus the `.par` `STREAM0.P_B` through parasolid-kit. Load the schema from the user's Solid Edge `Schema` folder, which can be found automatically under `C:\Program Files\Siemens\Solid Edge *\Schema`. Fall back to the display mesh (`Display/Cache*` or the asm `Preview/Display`) when a body does not convert exactly.
2. Validate against the owner's STEP export of the assembly once it arrives: occurrence count and names, transforms, and per-part volume, bbox and face count.
3. With Solid Edge allowed at development time, make 3–4 controlled samples:
   - a 2-part asm with a known offset and rotation, to confirm the `Attachments` layout;
   - a part with a fillet, a swept face and a shell, to cover the blend, swept and offset surfaces.

   Do not spend time on the feature history.

## Files (scratchpad)
- `j-separse-out/j-separse-streams.txt`: OLE listings for the pin .par and the .asm
- `j-separse-out/xt/`: all 38 extracted Parasolid streams (`.P_B` = partition = .x_b, `.D_B` = deltas)
- `j-separse-out/step/j-separse-*.step`: OCCT-built STEP files (Krytka, pin, M3 screw, pad, eccentric pin, insert)
- `j-separse-out/j-separse-asm-placements.json`: 209 occurrences with R and t in mm
- `j-separse-out/j-separse-pin3x10-check.json`: parasolid-kit report
- Scripts: `j-separse-list.py`, `j-separse-extract.py`, `j-separse-brep2.py`, `j-separse-xt2occ.py`, `j-separse-asm3.py`
- Venvs: `j-separse-venv` (olefile, parasolid-kit) and `j-separse-venv2` (same packages, using the system OCP 8)
- `j-separse-schema/sch_13006.sch_txt`: a local copy from the Solid Edge install, for testing only; do not commit or redistribute
