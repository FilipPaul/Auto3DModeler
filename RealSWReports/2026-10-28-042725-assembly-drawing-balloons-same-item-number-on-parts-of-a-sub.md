# Assembly drawing balloons: same item number on parts of a sub-assembly / qty mismatch

- **Kind:** bug
- **Date:** 2026-10-28 04:27:25
- **App version:** 0.9.0 (main @ 5f7e65b, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

User checked the drawing sets of "Assembly 3" (P12 → sheet P24) and "Mechanismus – rameno na ložisku" (P6 → sheet P23). Balloon "2" seems to point to different objects. Assembly 3 holds: item 1 = sub-assembly Mechanismus (which itself contains an ISO 4762 M1.6×5, its I4), item 2 = ISO 4762 M1.6×5 (top-level I2, qty 1). So a screw of the same part number exists both at the top level and inside the sub-assembly; the user saw balloon 2 on more than one object while the parts list says qty 1. In Mechanismus' own sheet item 2 is the bearing 608-2Z (own numbering per sheet, which is fine). The agent cannot see balloons via get_sheet (no balloon list), so it could not verify which instances carry which balloon.

## What was expected

Recommendation (ISO 6433 / ISO 7573 practice):
1) One item number = one part number within a drawing's parts list; identical parts share the number and the QTY column says how many (e.g. two screws at the same level → item 2, qty 2), NOT two different numbers and NOT the same number with qty 1.
2) One balloon per item, attached to one visible instance (optionally several leaders from the same balloon, or "2×" next to it). Do not repeat the balloon on every instance.
3) Sub-assemblies: on the top-level drawing, a sub-assembly is one item (balloon 1 on the sub-assembly as a whole); parts inside it are NOT ballooned at the top level and are not counted in the top-level qty — they are itemized on the sub-assembly's own sheet. So in Assembly 3 balloon 2 must point only to the top-level screw (qty 1); the screw inside Mechanismus belongs to item 1. Balloon numbers being different between the two sheets (2 = screw on Assembly 3, 2 = bearing on Mechanismus) is correct — each sheet numbers its own list.
4) Optional: a "flattened" BOM export (bom CSV) may sum identical part numbers across levels (screw total qty 2), but the drawing's parts list stays per level.
5) get_sheet for assembly sheets should list balloons (item number, part, which placed instance I..., position) so the AI can verify them; ideally a check flag for "balloon count/instances vs qty mismatch".

## Steps

list_parts; open_part P12 + get_assembly (I1 = sub-assembly P6, I2 = ISO 4762 M1.6×5 qty 1); open_part P6 + get_assembly (I4 = ISO 4762 M1.6×5 inside); get_sheet on P24 shows only dims and views, no balloons; get_screenshot does not work on a sheet.

## Workaround

Explained the correct practice to the user; could not inspect the balloons directly.
