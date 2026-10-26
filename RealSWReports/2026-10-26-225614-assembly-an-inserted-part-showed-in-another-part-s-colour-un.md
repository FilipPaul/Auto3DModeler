# Assembly: an inserted part showed in another part's colour until its model was reopened

- **Date:** 2026-10-26 22:56:14
- **Reported by:** the AI agent (MCP report_problem)

## What happened

In a new assembly, Kačer (P2, a duplicate of Kačenka with its own set_look yellow + painted faces) showed blue (#4FA8E8, the look of Bazének P3, the model made just before) and see-through. set_look I4 #FFD400 did not change the view. After open_part P2 and going back to the assembly it showed yellow (all faces, the painted ones too); set_look I4 null then gave its own colours.

## What was expected

The placed part shows its own colours (look + painted faces) right after insert_part.

## Steps

duplicate_part (Kačenka -> Kačer), add features + paint_faces; new_model Bazének + set_look #4FA8E8; new_model Voda + set_look opacity 0.4; new_assembly; insert_part P3, P4, P1, P2; place_part I4 with turn [z, z]; get_screenshot.

## Workaround

open_part P2, back to the assembly, set_look I4 color null.

## Resolved

- **2026-10-26** — Explained and fixed: the part just put in was the chosen one, drawn all in the selection blue (#6CB6FF, close to Bazének's #4FA8E8), which hid its colour and painted faces — and set_look seemed to do nothing until it was no longer chosen. A chosen part now keeps its colours and painted faces and only glows blue (web/js/assembly/assembly.js). Test: tools/e2e_reported.py (3).
