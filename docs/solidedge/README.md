# Solid Edge interoperability — analysis only (2026-10-30)

Nothing here is implemented in the app. The owner asked for a quick analysis to pick up later.

Rules (from the owner): the app must never use or require Solid Edge. At development time the Solid Edge 2025 on the
owner's PC may be used to test macros and to make sample files.

- [file-format-analysis.md](file-format-analysis.md) — reading `.par` / `.asm` without Solid Edge: OLE container,
  Parasolid XT body (`PARASOLID/STREAM0.P_B`), assembly placements, feature data; verdicts and effort per item.
- [export-macro-analysis.md](export-macro-analysis.md) — exporting our parts as a Solid Edge macro (`.vbs`) that
  rebuilds them natively with sketches, dimensions and features; API mapping, versions, test plan, effort.
- [probe/](probe/) — the throw-away probe scripts the analysis used (olefile + parasolid-kit, run in a scratch venv;
  paths inside point to the analysis scratchpad). Not app code; never ship Siemens schema files.
