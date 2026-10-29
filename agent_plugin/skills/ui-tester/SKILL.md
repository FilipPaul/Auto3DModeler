---
name: ui-tester
description: Use when the user types /uiTester (or asks you to test the app's GUI / buttons / workspaces) — design a few test parts, check for every feature you use that its GUI path exists, is reachable and does what the tool does (also in Czech), report each problem once, and end with a summary table.
---

# /uiTester: test the app's GUI like a careful user

You are the app's tester now. Build real things with the tools, and for every feature check the way a user would
reach it on screen. Tell the user in one line what you will test, then go — no questions unless something blocks you.
If the user added words after /uiTester ("only the sheet"), test only that.

## 1. The test designs (keep each small)
1. **A part** — `new_model {name: "UI test part"}`: a sketch (a rectangle 60 × 40), an extrude (8 mm), a hole (Ø5
   through, on the top face), a pattern of the hole (a row of 3), a fillet on the vertical edges (2 mm). Check
   `get_model` (all ok) and that the volume is about what it should be.
2. **An assembly** — a second small part (a pin Ø4.8 × 20), `new_assembly`, `insert_part` both, `snap_faces` the pin
   into a hole (axis) and onto the top (touch); `get_assembly`: the pin turns only (free: turn), `check_collisions`.
3. **A drawing sheet** — `sheet_open` of the test part: views, dimensions (`get_sheet`), a title (`sheet_edit
   {texts: {title: "UI test"}}`).

## 2. For each feature you used: its GUI path
For every step above (sketch, extrude, hole, pattern, fillet, insert, joint, sheet, title…):
- **Exists and is reachable**: `gui_state {where: "tools"}` / `"panel"` / `"bar"` lists a control for it (label,
  tooltip, not greyed out when it should work). A command hidden in a menu counts if the menu's label says what is in it.
- **Does what the tool does**: `gui_action {control: …}` opens its panel; set a value the way the user would
  (`gui_action {control: "<box label>", value: …}`), OK / Finish, then `get_model` / `get_assembly` / `get_sheet` —
  the result must equal what the tool gave. Picks in the view: `gui_action {at: [x, y]}` (`get_screenshot` shows
  where); keys: Escape cancels, Delete deletes, ctrl+z undoes.
- **Czech**: click the top bar's **CZ** (`gui_action {control: "CZ"}`), `gui_state` again — every label and tooltip
  must be Czech (English words left = a ui problem: list them); **EN** switches back. Do this once per workspace.
- **Intuitive**: the panel opens with good defaults (works with one click), says in plain words what to pick, the
  OK / Finish / Cancel buttons are bottom-right of the view, an error says how to fix it.
Undo your test clicks you do not need (`undo`) so the designs stay clean.

## 3. Report each problem — once
- First `list_reports {search: "<the main words>"}`: if it is there, do not file it again (note "known" in your table).
- A wrong result, an error that should not happen, a control that does nothing → `report_problem {kind: "bug", title,
  what, expected, steps}` (steps: the gui_action / tool calls, so a developer can repeat it).
- Hard to find, English left in Czech, a surprising control, no good default → `report_problem {kind: "ui", …}`.
- A tool missing (you had to work around it, or a GUI feature has no tool) or a GUI control missing (a tool has no
  button) → `report_problem {kind: "tool request", …}` with the tool / control you would want: name, inputs, result.
- If report_problem answers "a similar report exists", it is known — count it as known, do not force it.

## 4. End with a summary table
One short table to the user, a row per feature tested:

| Feature | Tool | GUI path | Czech | Result |
|---|---|---|---|---|
| Hole | ok | ◎ Hole → face → OK: ok | ok | ✓ |
| Pattern | ok | not found in the toolbar | — | ui report (new) |

Then one line: how many checked, how many problems (new reports / already known), and where the reports are
(RealSWReports). Leave the test parts in the project (the user can delete them) unless they asked otherwise.
