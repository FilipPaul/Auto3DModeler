# Assembly sheet: dimension check asks for every part's details; balloon 1 points at the rod, not the base plate

- **Kind:** bug
- **Date:** 2026-10-29 01:56:08
- **App version:** 0.9.0 (main @ 63d5c3a, 2026-10-28)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

sheet_open on the assembly "Klikový mechanismus": check.fully_dimensioned false with 30 'missing' items that are part details — bought bearing 608-2Z inner Ø15.84 / Ø14.16, base plate's Ø6.6 / Ø12 / Ø22 holes, crank R13, rod R9 and many edges. An assembly drawing is never 'complete' this way. Also balloon pos 1 (Základová deska, I1) leader ends at nearly the same point as pos 4 (Ojnice) in the middle of the rod in the Iso view — it looks like it points at the rod.

## What was expected

For an assembly, the check asks only for assembly-level sizes (overall sizes, interface / mounting sizes, stroke) — never the inner geometry of bought parts; part details belong to the parts' own sheets. A balloon's leader ends on a visible face of its own part, away from other parts' leaders (on the base plate: its free top surface or a corner).

## Steps

Assembly with base plate I1, bearing I2, crank I3, rod I4 (lying above the base), slider I5; sheet_open -> get_screenshot of the sheet.
