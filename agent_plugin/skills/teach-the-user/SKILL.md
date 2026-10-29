---
name: teach-the-user
description: Use when the user asks how to do something in the app, where something is, or says "show me" / "teach me" / "jak…" / "kde je…" / "ukaž mi" — lead them through the app's own buttons step by step with gui_highlight instead of only describing it or doing it for them.
---

# Teach the user: show where, step by step

The user wants to learn the app, not only get a result. Point at the real controls on their screen, one at a time,
and let them click. Do the step yourself only when they ask you to.

0. **Suggestions first.** Most work in the app goes through the suggestions table: the user selects something (a
   face, an edge, a part, a dimension) and a small table in the view's corner offers what fits it. Lead them that
   way when it can be done there: show them what to click in the view (`gui_highlight {at: …}` — `gui_action {pick:
   "F2:end"}` answers where that face is on screen, `at` — it clicks it, so `gui_action {key: "Escape"}` after it
   leaves the click to the user), then, once the table shows, `gui_state {where: "suggest"}`
   and `gui_highlight {control: <the row's n>, text: …}` on the row. A row under ⋯ Show all: highlight ⋯ Show all
   first (its n is `show_all`). The toolbar is the second way — use it when nothing needs to be selected first.
1. **Find the control**: `gui_state {where: "tools"}` (the workspace's toolbar), `"panel"`, `"bar"` (the top bar) or
   `"view"` — each control has its `n` and `label` (with its tooltip). If what you need is not listed, it is inside
   something closed (a menu ▾, a panel, another workspace): show the thing that opens it first.
2. **Show it**: `gui_highlight {control: "<label or n>", text: "<what to do there, one short sentence>", step: "1/3",
   wait: true}` — a pulsing ring around it with your tip, the rest dimmed. Write the tip in the user's language and
   say what will happen ("Click ✏ Sketch to start a drawing on a plane."). A spot of the 3D view or a drawing:
   `at: [x, y]` — the pixels of the spot in your last `get_screenshot` picture (e.g. a face to pick).
3. **Wait for them**: with `wait: true` the call answers when the user clicked it ("the user clicked it"), closed
   the tip (Esc / ✕ — ask whether to go on) or did not click in time (show it again, or explain it another way).
4. **Look what changed** (`gui_state`, `get_screenshot`) and show the next step. The steps of a typical lead:
   - a new 3D model: ＋ New 3D model → ✏ Sketch → a plane (Top) → a shape tool → the size boxes → Finish sketch →
     ⬆ Extrude → its depth → OK;
   - a hole: the face (`at:` on it) → the table's ◎ Hole here → Ø → OK;
   - an assembly: ＋ Insert part ▾ → a part → 🔗 Joint → two faces → OK;
   - a drawing: 📄 Drawing sheet → a view / a dimension.
   Labels differ by workspace and language — always take them from `gui_state`, never from this list.
5. **End**: `gui_highlight {clear: true}` if a tip is still shown, then one line of what they learned and the
   shortcut, if any.

**Watching instead of showing:** when the user says "look what I'm doing" / "podívej se, co dělám" (a problem they
want you to see), `start_recording {reason}` and tell them to go ahead; when they say they are done,
`get_recording` (`stop_recording` if it still runs; `get_recording_screenshot {id}` for a shot) — the clicks, picks,
values and toasts in order; the toast texts and the moves just before them usually show the problem. Then lead them
the right way as above. Never start a recording unasked.

Rules
- One control per step; keep the tip under ~15 words. Do not click for the user (`gui_action`) while teaching,
  except to undo a wrong turn when they ask.
- A control that is greyed out: say what makes it usable (select something first, finish the sketch…).
- If the user could not find something they needed, or a control did what they did not expect, that is a UI
  problem: `list_reports {search: "<the words>"}`, and if it is not there, `report_problem {kind: "ui", …}`.
- If no control exists for what they want (only a tool does it, or nothing), say so and write
  `report_problem {kind: "tool request", …}` at once (after `list_reports` — report each thing once).
