---
name: suggest-features
description: Use when the user types /suggest or asks for ideas / new features / what the app is missing — propose a few concrete new features, and file the ones the user agrees to as tool requests (each once).
---

# /suggest: propose new features

1. **Know what is there and what is asked already**: the tools you have (your tool list), the workspace on screen
   (`gui_state`), and `list_reports {kind: "tool request"}` — the requests filed before (do not propose those as new;
   you may say they are waiting).
2. **Think from the user's work**: what they did in this chat, what took you several calls or a workaround, what a
   designer in SolidWorks / Fusion / PrusaSlicer would expect here. Keep each idea simple (few inputs, a good default,
   one click) — tools that need many inputs are not wanted.
3. **Propose 3–5**, briefly: a name, what it does for the user, the tool (name, inputs, result) and the GUI control
   (where it would sit). Then ask which to file: `ask_user {question: "Which ones should I report to the developers?",
   options: [...], recommended: 0}` (your best one first; an option "All of them") and end the turn.
4. **File the chosen ones**: `report_problem {kind: "tool request", title, what (what is missing and why it helps),
   expected (the tool and the control: name, inputs, result), workaround (how it is done today, if at all)}`. If it
   answers "a similar report exists", tell the user it is asked already.
5. One line at the end: what was filed (titles) and that the reports are in RealSWReports.

Also without /suggest: whenever you had to work around a missing tool during any task, file the
`report_problem {kind: "tool request", …}` at once (after `list_reports {search}`), then tell the user in one line.
