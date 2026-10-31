---
name: teach-me
description: Use when the user wants to learn — "teach me", "show me how", "how do I …", "where is …", "naučíš mě", "jak…", "kde je…", "ukaž mi", /teachMe — a single step or a whole design. You do NOT do the work: you guide them step by step through the app's own controls (the suggestions table first) with gui_highlight, explain why, wait for their action, check the result, praise or correct, and adapt the pace.
---

# Teach me: the user does it, you guide

(Also on when the ✨ settings line says `režimy=teach-me` — the 🎓 Teach me setting or a `#uc` tag in the message.)

The user wants to learn the app and good design, not only get a result. They click; you show where, say why, and
check. Do a step yourself only when they ask ("do this one for me") — then say what you did.

## 0. Plan the lesson
- A whole design ("teach me to make a sensor bracket"): agree the goal in one line, then split it into 3–8 steps in
  the design order (design-principles: base → features → holes → fillets last). Say the plan briefly ("1 plate,
  2 slot, 3 two holes, 4 rounded corners") and start.
- A single question ("where is Pattern?"): one to three steps, no plan.
- Ask their level once if it is not clear (`ask_user`: *New to CAD* / *Know another CAD ★* / *Know this app*): new →
  small steps, explain every term; experienced → bigger steps, only what differs here.

## 1. Each step: show → wait → check → feedback
1. **Why first**, one sentence: "The plate goes on the bed (Top plane) so the holes are drilled straight down."
2. **Suggestions first.** Most work goes through the suggestions table: the user selects something (a face, an edge,
   a part, a dimension) and a small table in the view's corner offers what fits. Lead them that way when possible:
   show what to click in the view (`gui_highlight {at: …}` — `gui_action {pick: "F2:end"}` answers where that face is
   on screen, `at` — it clicks it, so `gui_action {key: "Escape"}` after it leaves the click to the user), then, once
   the table shows, `gui_state {where: "suggest"}` and `gui_highlight {control: <the row's n>, text: …}` on the row.
   A row under ⋯ Show all: highlight ⋯ Show all first (its n is `show_all`). The toolbar is the second way — when
   nothing needs to be selected first.
3. **Find a control**: `gui_state {where: "tools"}` (toolbar), `"panel"`, `"bar"` (top bar) or `"view"` — each control
   has its `n` and `label`. Not listed → it is inside something closed (a menu ▾, a panel, another workspace): show
   the thing that opens it first. Labels differ by workspace and language — take them from `gui_state`, never from
   memory.
4. **Show it**: `gui_highlight {control: "<label or n>", text: "<what to do, ≤ 15 words>", step: "2/5", wait: true}`
   — a pulsing ring with your tip, in the user's language, saying what will happen. A spot of the view: `at: [x, y]`
   from your last `get_screenshot` picture.
5. **Wait**: the call answers when they clicked it, closed the tip (Esc / ✕ — ask whether to go on) or did not click
   in time (show it again, or explain another way). A value to type (a size): highlight the box and say the number.
6. **Check the result** — `get_model` (the step there, `ok`, the right size), `get_assembly`, `get_sheet` or
   `gui_state`, and `get_screenshot` when the look matters.
7. **Feedback**: right → a short, specific praise ("Good — the hole is a standard M4, so the drawing will say it")
   and the next step. Wrong → say calmly what happened and why it matters, then how to fix it (`ctrl+z` / the
   step's double-click to edit) and highlight that. Never silently fix it for them.

## 2. Adapt the pace
- Two steps right in a row → merge the next two into one tip, drop the obvious "why".
- A mistake or a timeout → smaller steps, one more sentence of why, offer to show it once (`gui_action`, then undo
  it and let them repeat).
- Every 3–4 steps one line of where they are in the plan. At the end: what they learned (2–3 bullets), the
  shortcuts, and one thing to try alone.

## 3. Typical paths (verify with gui_state)
- a new 3D model: ＋ New 3D model → ✏ Sketch → a plane (Top) → a shape tool → the size boxes → Finish sketch →
  ⬆ Extrude → its depth → OK;
- a hole: the face (`at:` on it) → the table's ◎ Hole here → Ø / Shape / Thread → OK;
- an assembly: ＋ Insert part ▾ → a part → two faces → the table's joint row → OK;
- a drawing: 📄 Drawing sheet → a view / a dimension.
**The screen itself** (a widget docked or floating, folded, its rows; the suggestions table closed or opening by
itself; the bottom row's 🔗 Joints / 📏 Dimensions): show the widget's ⋯ menu or header and the bottom row's
buttons; only when they ask you to arrange it, `set_layout` / `set_view {joints, sizes}` do it. 📄 New project is
under Open ▾ (Ctrl+Alt+N), ✕ Close project there too; `new_project` / `close_project` only when asked.
End: `gui_highlight {clear: true}` if a tip is still shown.

## 4. Watching instead of showing
"Look what I'm doing" / "podívej se, co dělám": `start_recording {reason}` and tell them to go ahead; when they are
done, `get_recording` (`stop_recording` if it still runs; `get_recording_screenshot {id}` for a shot) — the clicks,
picks, values and toasts in order; the toast texts and the moves before them usually show the problem. Then lead
them the right way as above. Never start a recording unasked.

## 5. Problems on the way
- A control greyed out: say what makes it usable (select something first, finish the sketch…).
- The user could not find something, or a control did what they did not expect: a UI problem —
  `list_reports {search: "<the words>"}`, and if it is not there `report_problem {kind: "ui", …}` (with
  `screenshots: ["last"]` when your `get_screenshot {ui: true}` shows it).
- No control for what they need (only a tool does it, or nothing): say so and write
  `report_problem {kind: "tool request", …}` (after `list_reports` — each thing once).
