# Screenshots not fitted to the part; set_view section:null keeps the cut; no screenshot of a sheet

- **Kind:** bug
- **Date:** 2026-10-28 04:30:30
- **App version:** 0.9.0 (main @ 5f7e65b, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

1) get_screenshot iso / back on the 60×40×45 bracket "Test – úhelník" shows only a zoomed-in part of the model (ends cropped), so text, fillets and holes could not be checked visually. 2) set_view {view: "iso", section: null} answered "View iso, cut along y at 0 mm": the section stayed on (switched axis to y). section: false removed it. 3) get_screenshot fails while a drawing sheet is on screen ("No part is open"), so the AI cannot check balloons or layout of a sheet. 4) After the chamfer step the iso screenshot showed odd colours (wall gold, plate blue), probably a selection / highlight left over in the screenshot.

## What was expected

1) Screenshots zoom to fit the whole body (or a fit:true option). 2) section:null removes the section as documented. 3) get_screenshot renders the sheet when a sheet is on screen. 4) Screenshots without selection highlights (or say what is highlighted).

## Steps

new_model "Test – úhelník"; base 60×40×5, wall on {datum XZ, offset 20} extrude 5 flip; holes, pattern, slot, rib + mirror, decal, fillet, chamfer; get_screenshot iso/back; set_view {section:{axis:x,offset:-26}} then {section:null}.

## Workaround

Used a section view to check the rib; section:false to clear it.
