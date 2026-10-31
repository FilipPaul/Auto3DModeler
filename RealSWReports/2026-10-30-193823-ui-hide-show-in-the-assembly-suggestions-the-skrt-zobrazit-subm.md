# Hide / show in the assembly suggestions: the 'Skrýt / zobrazit…' submenu is unintuitive — should open its own picker lis

- **Kind:** ui
- **Date:** 2026-10-30 19:38:23
- **App version:** 0.9.0 (main @ 5abdf57, 2026-10-30)
- **Reported by:** the AI agent (MCP report_problem)
- **Project:** `2026-10-30-193823-ui-hide-show-in-the-assembly-suggestions-the-skrt-zobrazit-subm.a3d` (open it in the app: 📂 Open ▾ › File…) — 22 part(s): Base, Plate B, Plate A, Column, Block, Shaft, L bracket, Housing (STEP), ISO 4762 M4×25, ISO 7089 M4 washer, ISO 4032 M4 nut, ISO 4762 M3×12, ISO 7089 M3 washer, ISO 4032 M3 nut, ISO 4762 M5×20, ISO 7089 M5 washer, Bearing 608-2Z, Standoff M3 MF 10 mm, Module A, Bearing block, Machine, SMC CDQ2B12-15DZ; 47 kB
- **Recording:** `2026-10-30-193823-ui-hide-show-in-the-assembly-suggestions-the-skrt-zobrazit-subm.recording.json` (⏺ the user's moves: 26 events over 54 s, stopped; without screenshots)
- **Screenshots:** 1 (below): `2026-10-30-193823-ui-hide-show-in-the-assembly-suggestions-the-skrt-zobrazit-subm.shot-1.png`

## What happened

User selected a part face in the assembly (Plate B I67) and clicked '👁 Skrýt / zobrazit…' in the suggestions table. It only toggles a ✓ and expands a '👁 Zobrazení' section appended at the bottom of an already long (22 rows) table, in the same list as joints / part actions. The user clicked it 4× (on/off/on/off), scrolled, zoomed, re-selected parts and opened '⋯ Ukázat vše' trying to find what happened; after ~50 s they finally found '◐ Zprůhlednit'. Recording: clicks at 0:02, 0:04, 0:06, 0:17, 0:34, then 'Zprůhlednit' at 0:50. User's words: 'Skrývání je extrémně neintuitivní… po kliknutí na skrýt/zobrazit by spíš nastavení zobrazení mělo vyskočit do nového výběrového seznamu místo zobrazení submenu.'

## What was expected

Clicking '👁 Skrýt / zobrazit…' should REPLACE the suggestions table with a new, short picker list (its own title 'Zobrazení – Plate B I67', a ← Zpět row) holding only the display options: Skrýt (H), Zprůhlednit, Znovu neprůhledně, Izolovat (Alt+H), Zprůhlednit ostatní, Zobrazit vše (Shift+H). Choosing one applies it and closes / returns to the table. No inline expandable section at the end of a long table, no ✓ toggle state on the row.

## Steps

Assembly 'Machine' → click a face of Plate B I67 → suggestions table → '👁 Skrýt / zobrazit…' → the section appears at the bottom of the table (rows 984–988), easy to miss.

## Screenshots

![the '👁 Zobrazení' submenu expanded at the bottom of the long suggestions table, below Vyjmout / Výkres dílu](2026-10-30-193823-ui-hide-show-in-the-assembly-suggestions-the-skrt-zobrazit-subm.shot-1.png)
*1. the '👁 Zobrazení' submenu expanded at the bottom of the long suggestions table, below Vyjmout / Výkres dílu*
