---
name: bug-hunter
description: Use when the user types /uiTester or /bugHunter, or asks you to test the app, hunt bugs or "do it like a user would" — do the user's task (or a set of test designs) ONLY through the GUI (gui_state, gui_action, get_screenshot ui) like a human, use the model tools only to verify, and report every bug, confusing UI and missing tool once with report_problem; end with a summary table.
---

# Bug hunter: work like a user, report what breaks

You are the app's tester now. Tell the user in one line what you will do, then go — no questions unless something
blocks you. Words after the command narrow it ("/uiTester only the sheet": test only that).

## 0. The rule: hands on the GUI only
- **Do** everything with `gui_action` (clicks, picks, values, keys, drags, suggestion rows), as a person would.
  Look with `gui_state` and `get_screenshot {ui: true}` before and after each action.
- **Read-only tools only to verify**: `get_model`, `get_assembly`, `get_sheet`, `get_bom`, `find_refs`, `get_sketch`,
  `check_collisions`, `list_reports`. Never change the design with add_feature, edit_feature, snap_faces, sheet_edit,
  library_add …
- **No GUI way** to do a step = a finding (`report_problem {kind: "tool request"}` or `"ui"`). Only then do that
  step with the tool to carry on, and note it as the workaround.

## 1. The task
- The user gave a task ("make a bracket with two M4 holes"): do exactly that through the GUI.
- No task (plain /uiTester): build these small test designs, each through the GUI:
  1. **A part** — ＋ New 3D model, a sketch (a rectangle 60 × 40), Extrude 8, a hole (Ø5 through, top face), a pattern
     of the hole (a row of 3), a fillet on the vertical edges (2 mm). Verify `get_model` (all ok, volume ≈ expected).
  2. **An assembly** — a second part (a pin Ø4.8 × 20), a new assembly, both inserted, the pin into a hole (Concentric)
     and onto the top (Touch); verify `get_assembly` (the pin turns only) and `check_collisions`.
  3. **A drawing sheet** of the test part: views, a dimension, the title "UI test"; verify `get_sheet`.

## 2. Each step: suggestions first, then the toolbar
The app is meant to be worked through its **suggestions table** (about 90 % of the everyday work):
1. **Select** as the user would: `gui_action {pick: "F2:end"}` (a face; an assembly's part `"I2"`, its face
   `"I2 F2:end"`), `{at: [x, y]}` (pixels of your last `get_screenshot`, an edge too), or a sheet's dimension / view
   `{control: <its n>}`. Several: then `gui_action {pick: …, mods: ["ctrl"]}` (Ctrl+click).
2. **Read the table**: `gui_state {where: "suggest"}` — `title` / `about` must name what you selected; `rows` top to
   bottom (`rank_pos` 1 = most relevant), `more` / `all` = under ⋯ Show all. `get_screenshot {ui: true}`: where it
   sits, whether it covers the part.
3. **Run the expected row**: `gui_action {suggest: "<label>"}`, fill its panel (`gui_action {control: "<box>", value}`),
   OK — then verify with the read tools.
4. **Judge it**: not offered → ui / tool request; only under ⋯ Show all, or not in the top 3 for its obvious selection
   (a hole on a flat face, a joint for two faces) → ui, naming its `rank_pos`; a label that does not say what it does
   → ui.
Then the toolbar path for the same step: `gui_state {where: "tools"}` / `"panel"` / `"bar"` lists it (label, tooltip,
not greyed out when it should work); a command inside a menu counts if the menu's label says what is in it.

## 3. What else to look at on every screen
- **Result = intent**: the size you typed is the size in `get_model`; the face you picked is the one used.
- **Keys**: Escape cancels, Delete deletes, ctrl+z undoes (`gui_action {key: "ctrl+z"}` then verify).
- **Czech**: once per workspace `gui_action {control: "CZ"}`, `gui_state` — every label and tooltip Czech (English
  left = ui: list them); **EN** back.
- **Intuitive**: one click works with good defaults, plain words say what to pick, OK / Finish / Cancel bottom-right
  of the view, an error says how to fix it, no native browser dialogs.
- **Newer features** (once each when the test is not narrowed): drag a made hole on its face (`gui_action {at,
  drag_to}`: it snaps, a 🔒 size holds) and its Shape / Thread / Depth / Size rows; ⚙ Mechanism ⇤ min / max ⇥; a cable
  harness's point list (＋, ✕, ↑ ↓), 📎 clip, ⛓ chain; a sheet's ± / fit / Ra chips and ⇄ Move to another view; the
  widgets' ⋯ menus (dock, float, Rows) and the suggestions' ✕ / Automatically; the bottom row's 🔗 Joints / 📏
  Dimensions; 📏 Measurements; 🕘 Versions; ⏺ recording.
Undo test clicks you do not need so the designs stay clean.

## 4. Report each finding — once
- First `list_reports {search: "<main words>"}`: there → do not file it again ("known" in your table).
- Wrong result, an error that should not happen, a control that does nothing → `report_problem {kind: "bug", title,
  what, expected, steps}` — steps = your gui_action calls, so a developer can repeat it.
- Hard to find, English in Czech, surprising behaviour, no good default → `report_problem {kind: "ui", …}`.
- No GUI way for a step, or no tool for a GUI feature → `report_problem {kind: "tool request", …}`: the control /
  tool you would want (name, inputs, result) and the workaround.
- Visible problems (a missing control, a menu covering another, a rendering glitch): `get_screenshot {ui: true}`,
  then `screenshots: [{shot: "last", caption: "<what it shows>"}]` (or `"view"`); up to 4, only when it helps.
- "A similar report exists" → it is known; do not force it (`again: true` only for a really different problem).

## 5. Summary table
| Step | GUI path | Suggestion (rank) | Verified | Czech | Result |
|---|---|---|---|---|---|
| Hole | face → ◎ Hole here → OK | ◎ Hole here (2) | Ø5 ok | ok | ✓ |
| Pattern | — | under ⋯ Show all | via tool (workaround) | — | ui + tool request (new) |

Then one line: steps done, findings (new / known by kind), where the reports are (RealSWReports). Leave the test
parts in the project unless the user asked otherwise.
