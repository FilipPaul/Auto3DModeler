# Extrude cut with draft removes nothing on a profile made of arcs

- **Kind:** bug
- **Date:** 2026-10-29 20:35:52
- **App version:** 0.9.0 (main @ 92d0e37, 2026-10-29)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

A cut extrude (d 11, draft 25°) of a closed sketch profile made of 14 arcs (a scalloped oval on plane YZ offset 38) says "The cut removes nothing" (volume change 0.003 mm³), although it went -x through the body over 27 … 38. The same extrude with draft 0 cuts 6682 mm³ as expected.

## What was expected

The draft cut removes material with its side walls leaning in; if a draft cannot be built for that profile, an issue says so (not a silent empty cut).

## Steps

Lahvička jablko: rollback to F2; sketch F4 on {datum: YZ, offset: 38}: profile [[16,33],{arc:[16.87,36.18]},[14.42,38.64],… 14 arcs]; extrude F5 {op: cut, d: 11, draft: 25}.

## Workaround

Draft 0: straight walls.
