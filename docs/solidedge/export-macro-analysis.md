# Solid Edge macro export: analysis for next time (job j-semacro, 2026-10-30)

Status: analysis only. No code in the repo was changed and nothing was committed. No Solid Edge process was started.
The API facts below come from Solid Edge 2025's own type libraries (`C:\Program Files\Siemens\Solid Edge 2025\Program\*.tlb`),
read offline with pywin32 in a scratch venv (`j-semacro-tlb.py`, `j-semacro-tlb2.py`; full dump in `j-semacro-tlb.txt`, all
in this scratchpad). Nothing has been run against a live SE yet, so every call below is **unverified at runtime**.

## 1. Macro format: recommend `.vbs` (VBScript, late-bound COM)

| Option | Runs with no installs? | Notes |
|---|---|---|
| **.vbs** (double-click, or `cscript x.vbs out.par`) | Yes, on every Windows | `GetObject(, "SolidEdge.Application")`, then `CreateObject` if SE is not running. It's late-bound, so there's no type library or version binding, which makes it the most robust option across SE versions. One plain-text file that engineers can read and edit. |
| VB.NET / C# for SE's **Macro** command | Needs a compiled .exe/.dll, or the SE macro host | Needs a build step (we have none), and the interop assemblies are tied to an SE version. |
| Python | Needs Python + pywin32 | Rules itself out for most engineers. |
| PowerShell .ps1 | Yes | Blocked by the default execution policy on many company PCs. COM arrays and ByRef out parameters are clumsy. |

Risks with .vbs:
- Microsoft is phasing VBScript out. In Windows 11 24H2 it is a Feature-on-Demand that is still on by default, and it is planned to be off by default later (around 2027). The fallback would be the same script as **VBA** (the text is almost the same) pasted into SE's or Excel's VBA editor, so the generator should keep the VBS free of WScript-only calls outside a small header.
- VBScript passes only Variant arrays. Calls that take `ProfileArray` / `EdgeSetArray` (`AddFiniteMulti`, `Rounds.Add`, …) have to be checked live to see whether they accept `Array(obj)` (a SAFEARRAY of VARIANT). This is the first thing to test. Where SE insists on typed arrays, use the single-profile forms instead (`ExtrudedProtrusions.AddFinite(Profile, …)`, which takes no array).
- No enum names. Write the constants as numbers, each with a comment. Values confirmed from constant.tlb:
  `seModelingModeOrdered = 2`, `igLeft = 1`, `igRight = 2`, `igSymmetric = 3`, `igBoth = 6`, `igNormalSide = 2`, `igReverseNormalSide = 1`, `igQueryAll = 1`, `igRegularHole = 33`, `igCounterboreHole = 34`, `igCountersinkHole = 35`, `igTopPlane = 2`, `igRightPlane = 3`, `igFrontPlane = 4`, `igCounterboreProfileIsAtTop = 149`.

Macro skeleton:
- **Header:** attach to SE or start it, `Documents.Add("SolidEdge.PartDocument")`, `doc.ModelingMode = 2` (Ordered), `Set m = Nothing`.
- **Helpers:**
  - `P2(prof, u, v)`: our sketch u, v + frame → world metres → profile 2D, via `Profile.Convert3DCoordinate`. This makes any plane orientation work without guessing how SE orients a plane's axes. Also check the mirroring (determinant) and swap arc start/end when the mapping is mirrored.
  - `FindFace(cx, cy, cz, nx, ny, nz)` and `FindEdge(mx, my, mz, tx, ty, tz)` (see §2).
  - `Fail(step, msg)`: logs the problem and continues to the fallback.
- **One block per step:** `' F3 extrude "Boss" 10 mm`, then the calls.
- **Optional argument 1:** a path to save as `.par` (batch use, and how the e2e test drives it).

## 2. Mapping our features to the Solid Edge API (Ordered)

Units: SE takes metres and radians in the API, so write every length × 0.001.

| Ours (doc.py) | SE API (2025 type library) | Notes / hard parts |
|---|---|---|
| sketch plane `{datum: XY/XZ/YZ, offset}` | `doc.RefPlanes.Item(1..3)`; offset: `RefPlanes.AddParallelByDistance(ParentPlane, Distance, NormalSide, …)` | Check which `Item` is Top / Right / Front live (expected 1 = Top XY, 2 = Right YZ, 3 = Front XZ). |
| sketch on a face `{face: name, frame}` | `RefPlanes.AddParallelByDistance(<face>, 0, …)`, where `<face>` comes from `FindFace` | A face can be the parent plane. If no face matches: offset from the base plane when the normal is along an axis, else `AddAngularByAngle` chains. `AddBy3Points` needs edges, not points. |
| sketch | `doc.ProfileSets.Add()` → `.Profiles.Add(refPlane)` → `prof.Lines2d / Arcs2d / Circles2d / Points2d` → `prof.End(igProfileClosed)` | `End` validates the profile. Open profiles (sweep paths) must not be closed. One SE profile per closed region set; our holes inside one sketch are fine (SE takes nested loops). |
| line / rectangle / polyline | `Lines2d.AddBy2Points(x1, y1, x2, y2)` + `Relations2d.AddKeypoint(l1, 1, l2, 0)` to join the ends | Shared endpoints must be joined explicitly with keypoint relations. Otherwise they are only coincident and the dimensions don't drive the shape. |
| arc (centre, a → b counter-clockwise) | `Arcs2d.AddByCenterStartEnd(xc, yc, xs, ys, xe, ye)` | Direction depends on the profile's handedness; swap start/end when `P2` reports a mirror. |
| circle | `Circles2d.AddByCenterRadius(x, y, r)` | |
| slot | 2 lines + 2 arcs + tangent and keypoint relations | |
| spline / text / outline-of-face entities | not mapped (v1) → fallback | Text: SE has `TextProfiles`, but it's out of scope. |
| relations h / v | `Relations2d.AddHorizontal(l)` / `AddVertical(l)` | Every `Relations2d` call has a trailing `guaranteed_ok` argument (pass False). |
| parallel / perpendicular / equal / tangent / concentric / colinear | `AddParallel`, `AddPerpendicular`, `AddEqual`, `AddTangent`, `AddConcentric`, `AddColinear` | Our model stores few of these explicitly (h / v / tan / on / mid / mir / pat / off). Parallel / perpendicular / equal exist only as solved geometry or dims. |
| on, mid, coincident | `AddPointOn(obj, keyIndex, curve)`, `AddKeypoint(o1, i1, o2, i2)` | Key-point indexes: line 1 = start, 2 = end (0 might be "any"); check live. |
| mirror (`mir`) | `AddSymmetric(axisLine, o1, o2)` | |
| sketch pattern (`pat`), linked offset (`off`) | plain copies (geometry only) + a comment | SE profiles have no linked 2D patterns. |
| dims `len`, `dx`, `dy`, `dist`, `pl` | `prof.Dimensions.AddLength(line)`, `AddDistanceBetweenObjects(o1, x1, y1, z1, kp1, o2, …)` | Make them **driving** by setting `dim.Constraint = True` and then `dim.Value = v` (metres). Check the property names live. dx / dy need the dimension axis (`dim.MeasurementAxis…`). That is the fiddliest part. |
| dims `dia`, `rad`, `ang` | `AddCircularDiameter(circle)`, `AddRadius(arc)`, `AddAngleBetweenObjects(l1, …, l2, …)` | The angle's quadrant is picked by the key points / pick positions. |
| extrude add (first / later) | `m = doc.Models.AddFiniteExtrudedProtrusion(n, profArr, side, d)` / `m.ExtrudedProtrusions.AddFinite(prof, igRight, side, d)` | The first feature must come from `Models.Add…`, which creates the Model. `side` = `igRight` / `igLeft` (our flip), and symmetric = `igSymmetric` (3) in the `…Multi` / `Add` forms. Both sides with different distances (`d2`): the full `ExtrudedProtrusions.Add(… ExtentType1 …, ExtentType2 …)`. Draft angle: `TreatmentDraftAngle1`. |
| extrude cut / through all / up to next / up to face | `m.ExtrudedCutouts.AddFinite / AddThroughAll / AddThroughNext / AddFromTo(prof, side, from, to)` | `ProfileSide` decides which side of the profile is removed. Take the profile's interior: for closed profiles SE ignores it or needs `igRight`; check live. |
| revolve (axis x / y / a sketch line, angle) | `prof.SetAxisOfRevolution(line2d)` before `End`; then `Models.AddFiniteRevolvedProtrusion(…)` / `m.RevolvedProtrusions.AddFinite(prof, refAxis, side, planeSide, angleRad)` / `RevolvedCutouts.AddFinite` | The axis must be a Line2d in the profile. Our axis "x" / "y" becomes an extra construction line along the sketch axis. |
| hole plain / counterbore / countersink, through / depth | `hd = doc.HoleDataCollection.Add(HoleType=33/34/35, HoleDiameter, CounterboreDiameter, CounterboreDepth, CountersinkDiameter, CountersinkAngle, …)`; a profile with `Holes2d.Add(x, y)` per point; `m.Holes.AddFinite(prof, side, depth, hd)` / `AddThroughAll(prof, side, hd)`. `AddFiniteEx / AddThroughAllEx(…, bPhysicalThread)` exist in 2025 | **Hard part.** A hole profile is a special profile (`Holes2d`, one hole per point), and HoleData has 21 positional arguments. Safer v1: plain hole = circle extruded cutout; counterbore = two cutouts; countersink = `RevolvedCutouts` of a V profile. Then upgrade to real Holes once verified. |
| thread (M5…) | Hole with `ThreadDescription "M5x0.8"`, `ThreadMinorDiameter`, `ThreadDepth`; on a shaft: `m.Threads.Add(holeData, n, cylArray, cylEndArray, …)` | Cosmetic thread = HoleData with thread fields + `bPhysicalThread = False` (`…Ex`, newer SE only). Old SE: fall back to a tap-drill hole + a comment. |
| fillet / chamfer on edges | `m.Rounds.Add(nSets, Array(edgeSet), Array(r), …)`; `m.Chamfers.AddEqualSetback(nSets, Array(edgeSet), d)` | Edges come from `FindEdge` (below). `Rounds.Add` has 7 arguments in 2025; older SE took only the first 3 (the others optional). An edge set may need to be an `Edges` collection, not a VB array; check live. |
| shell | `m.Thinwalls.Add(ThicknessSide, t, OpenFaces, 0, Empty, Empty)` | `OpenFaces` from `FindFace`. The array question again. |
| pattern linear / circular of steps | `m.Patterns.AddByRectangular(nFeat, featArr, refPlane, nx, ny, sx, sy, angle, method, refIdx)` / `AddByCircular(nFeat, featArr, refPlane, count, angleSpacing, axisPoint, method, dir, arc)`; newer: `…Ex(…, PatternType)` | Our direction is an arbitrary 3D vector. Pick a ref plane that contains it and set `RectangleAngle`; circular needs a plane square to the axis and an axis point. **Hard.** Fallback: write each copy as its own repeated feature. That's exact and simple (sketch copied and moved), but not an SE pattern. |
| mirror (steps / body) | `m.MirrorCopies.Add(plane, nFeat, featArr)`; body: `MirrorCopies` of all features, or `Models.SaveAsMirrorPart` | Mirroring a face-plane needs `FindFace`. |
| split, loft, sweep, rib, draft, decal (text), harness, imported solid | not mapped in v1 | → fallback. Loft / sweep exist (`AddLoftedProtrusion`, `AddSweptProtrusion`) but take many arguments. |
| **fallback for the remainder** | `doc.Models.AddBodyFeature(ImportFileName)` (in 2025's type library) or `Models.AddCopiedPart(FileName, …)` | Embed our STEP (ASCII) in the .vbs as text, write it to `%TEMP%` at run time, then import it. Open questions: does `AddBodyFeature` take STEP or only Parasolid `.x_t`? And can it join an existing model? If not, stop native rebuilding at the first unsupported step, keep the native features in their own body, and add the full exact STEP body as a separate body / copied part, with a comment listing the skipped steps. |

**Face and edge references (the core hard part).** At export, our kernel resolves each referenced face and edge (we already
store names and `fp` points) into geometry:
- **face:** a point on the face and its normal, plus the face's area (to tell apart parallel faces that share a plane);
- **edge:** its midpoint and unit tangent, plus its length.

The macro's `FindFace` loops `m.Body.Faces(igQueryAll)` and scores each candidate:
- `Face.GetParamAtPoint` / `GetPointAtParam` distance to our point (within 1e-6 m), then `Face.GetNormal` at that parameter (dot > 0.999). `Face.GetRange` is a quick pre-filter.

`FindEdge` loops `m.Body.Edges(igQueryAll)`:
- `Edge.GetParamExtents` → mid-parameter → `GetPointAtParam` + `GetTangent`; match midpoint distance and |dot| of the tangents.
- Use `GetEndPoints` as a second check.

Each lookup happens right before its feature, so it sees the SE body as it is at that step. When nothing matches, the macro
logs it and goes to the fallback. Watch-outs:
- Our fillets round whole tangent chains (OCCT), while SE rounds only the picked edges unless `RollAcrossTangentEdges` is set. Pass True, or list every edge of the chain at export.
- Edge midpoints of full circles: SE may split a full circle into two edges (as OCCT does) or keep it as one, and the midpoint differs. Match on any point of the edge (`GetParamAtPoint` with a max deviation) rather than strictly the midpoint.

## 3. API version notes (2025 vs older)

- `ModelingMode` (Ordered / Synchronous) exists since ST1 (2008). Before ST, every part was ordered and the property does not exist, so wrap the call in `On Error Resume Next`. SE 2025 default templates may open in **Synchronous**, which is why the macro must set Ordered before the first feature.
- The `…Sync` methods (Synchronous) appear from ST1. Don't use them.
- `Holes.AddFiniteEx / AddThroughAllEx(bPhysicalThread)`, `HoleDataCollection.AddEx` (standard / size / fit / chamfers), `Patterns.AddByRectangularEx / AddByCircularEx(PatternType)`, `Models.AddCopiedPartEx`, `AddBodyFeature`, `Rounds.Add`'s extra roll arguments: these are newer additions, so use the plain forms. The exact SE version where each appeared is unknown offline. The macro can test with `On Error Resume Next` and fall back to the older call.
- Relations2d / Dimensions / Lines2d / Arcs2d / Circles2d calls have been stable since V1x, and so have `ExtrudedProtrusions.AddFinite`, `ExtrudedCutouts.AddThroughAll`, `RevolvedProtrusions.AddFinite`, `Chamfers.AddEqualSetback`, `Thinwalls.Add`, `MirrorCopies.Add` and `Patterns.Add` (with a pattern profile).
- The ProgID `SolidEdge.Application` is the same in all versions.
- Templates: use `Documents.Add("SolidEdge.PartDocument")` without a template path, which gives the user's default (ISO or ANSI). Units in the API are always metres, whatever the template shows.
- Target: write for the plain (non-Ex) forms, test on 2025, and state "tested on SE 2025; expected to work on ST7+ (no `Ex` / `Sync` calls)".

## 4. Test plan with the local SE 2025 (dev only)

1. Safety: `tasklist /FI "IMAGENAME eq Edge.exe"`. If any Edge.exe exists that we did not start, **skip** the test, because the macro's `GetObject` could attach to the owner's session. Then start our own instance from the scratch venv (`win32com.client.DispatchEx("SolidEdge.Application")`, `Visible = False`, `DisplayAlerts = False`) and remember its PID. Run `cscript //nologo part.vbs <scratch>\part.par`; the macro's `GetObject` finds our instance, the only one. Then `app.Quit()`, and kill that PID if it is still alive.
2. First smoke test: confirm `Array(profile)` into `AddFiniteMulti`, `Rounds.Add` with a VB array, the `RefPlanes.Item` order and `Convert3DCoordinate`. These decide the macro's style.
3. Per part: open the .par via COM, `doc.SaveAs <x>.stp`, read it with our kernel (`importers` / `K.volume`, `K.bbox`, face count), and compare with our own STEP export:
   - volume within 0.1 %;
   - bbox within 0.01 mm;
   - face count equal (warn rather than fail, because SE may split periodic faces differently).
   Also check `doc.Models.Item(1).Body` exists and `m.Features` count = the number of native steps.
4. Driving dims: change one `Dimension.Value` (e.g. the plate length) via COM, `doc.Recompute`, and check that the volume changed as computed analytically.
5. Parts:
   - a plate with holes + fillets (cutouts or Holes, Rounds, FindEdge);
   - a revolved part (axis line, RevolvedProtrusions);
   - a sketch on a face of an earlier extrude (FindFace + plane on face);
   - linear and circular patterns;
   - the demo parts (tools/make_demos.py), expecting partial fallback.
6. Unit tests (no SE): generate the macro for sample parts and check:
   - the calls are present;
   - lengths are in metres;
   - the comments list skipped steps;
   - the STEP fallback is embedded when needed.
7. `tools/e2e_solidedge_macro.py`: skipped when `SolidEdge.Application` is not registered or an Edge.exe is already running. Add it to `.claude/agents/tester.md`.
8. Afterwards, check that no Edge.exe we started is left and that `Documents\Zakládání` is untouched.

## 5. Effort estimate

| Piece | Estimate |
|---|---|
| Live SE smoke tests to settle the array / constant / plane-orientation questions | 0.5 day |
| Generator core (`auto3d/modeler/semacro.py`): header, `P2`, sketches (lines / arcs / circles / slots / points), keypoint joins, relations, driving dims | 1.5–2 days (dims dx / dy / angle are the fiddly part) |
| Extrude (all variants) + revolve + cutouts | 1 day |
| FindFace / FindEdge + fillet / chamfer / shell + sketch on face | 1–1.5 days |
| Holes (cutout v1, then real Holes + cosmetic threads) | 1 day |
| Patterns + mirror (or per-copy fallback) | 1 day |
| STEP fallback (embedding, AddBodyFeature / copied part) | 0.5–1 day |
| App wiring (Export menu item, server `MODEL_FILES`, worker op, AI `solidedge_macro` format + skill line + e2e_agent case, i18n, README) | 0.5 day |
| Unit tests + e2e round trip in SE + fixing what the round trip finds | 1.5–2 days |
| **Parts total** | **≈ 8–10 working days** |
| Assemblies (`.asm` macro: `Occurrences.AddWithTransform(par, ox, oy, oz, ax, ay, az)` for fixed positions; relations via `Relations3d.AddPlanar / AddAxial` with faces found by geometry in each occurrence; quick parts as STEP-converted .par) | +3–4 days for fixed positions, +3 days more for real mates |

## Findings so far (offline, from the type libraries)

- All the collections and methods named above exist in SE 2025, with these exact argument lists:
  - `ExtrudedProtrusions.AddFinite(Profile, ProfileSide, ProfilePlaneSide, Depth)`
  - `Holes.AddFinite(Profile, ProfilePlaneSide, FiniteDepth, Data)`
  - `Rounds.Add(NumberOfEdgeSets, EdgeSetArray, RadiusArray, RollAcrossTangentEdges, RollOrCapAcrossSharpEdges, RollAlongBlendEdges, ApplyVertexBlends)`
  - `Thinwalls.Add(ThicknessSide, CommonThickness, OpenFaces, NumberOfUniqueThicknesses, UniqueThicknessesArray, UniqueThicknessFaceListArray)`
  - `Patterns.AddByRectangular(…)` / `AddByCircular(…)`
  - `Profile.Convert3DCoordinate(x3d, y3d, z3d, x2d, y2d)`
  - `Edge.GetEndPoints / GetPointAtParam / GetTangent`
  - `Face.GetNormal / GetParamAtPoint`
  - `Dimensions.AddLength / AddCircularDiameter / AddRadius / AddDistanceBetweenObjects / AddAngleBetweenObjects`
  - `Relations2d.AddHorizontal / AddVertical / AddParallel / AddPerpendicular / AddTangent / AddEqual / AddConcentric / AddKeypoint / AddPointOn / AddSymmetric / AddColinear`, each with a trailing `guaranteed_ok`
  - `Variables.Add / Edit` (to name driving values: e.g. `Length = 0.08`).
- `Models.AddBodyFeature(ImportFileName)` exists. It is the most promising route for the "STEP body for the remainder" fallback; whether it takes STEP still needs a live test.
- `RefPlanes.AddBy3Points` takes edges and key points, not coordinates. Planes for arbitrary frames have to come from a face (offset 0) or from parallel / angular planes off the base planes.
