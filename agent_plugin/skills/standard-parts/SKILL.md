---
name: standard-parts
description: Use whenever you add a bought part (screw, nut, washer, dowel pin, insert, standoff, bearing, spring, probe, receptacle) to a design, when the user names a part number to use (its maker's STEP found online), and at hand-over. Keeps the number of different bought parts small — one screw size per job, a few lengths, one head type, the same pins and standoffs — and reports how many kinds the design uses.
---

# Few kinds of bought parts

Every extra part number costs: purchasing, stock, a wrong screw in assembly. A design with 3 screw kinds beats
one with 10 perfectly sized ones. Bought parts always come from the library (`library_search`, `library_add`).

## 1. Before you add any bought part
1. **What is used already**: `get_bom {mode: "summary"}` of the top assembly (rows with `make_buy` buy: maker, pn,
   total) or `get_assembly`'s parts list. In a single part: what its future assembly uses, if the user said.
2. **Reuse**: an item + size + length already in the BOM that does the job → `library_add {item, size, length,
   to: "assembly"}` with exactly those values (the same part again: one BOM row).
3. **New kind** only when nothing used fits (load, space, a standard the bought part dictates). Then
   `library_search {query}` within the preferred set below, and say why the new kind is needed.

## 2. The preferred set (unless the project or the user has its own)
| Function | Use |
|---|---|
| Structure: plates, brackets, frames | M4 (heavy frames M5 / M6) ISO 4762 socket head |
| Small parts: PCBs, sensors, covers | M3 ISO 4762 (M2.5 only where the bought part demands it) |
| Lengths | ≤ 3 per thread, from 6 · 8 · 10 · 12 · 16 · 20 · 25 · 30 |
| Heads | one per thread: socket head; countersunk ISO 10642 only where flush is functional; low head DIN 7984 only where height is missing |
| Washers, nuts | ISO 7089 washers only on slots and soft material; a nut only where no thread can be tapped |
| Dowel pins | ISO 8734 one Ø per project (Ø4 m6; Ø3 small, Ø6 big), lengths 12 · 16 · 20 |
| Standoffs | one family for all PCBs (e.g. M3 × 10 hex) |
| Inserts (printed parts) | one ruthex size per thread |
| Probes, receptacles | one series per grid (ict-fixture) |

## 3. Fit the design to the standard part, not the reverse
- Screw length L = clamped thickness + engagement (into Al 1.5–2 d, steel 1–1.5 d, a nut m + 2 pitches), rounded
  to a length already used. If it does not fit, change the design by 1–2 mm — a deeper thread, a deeper counterbore
  (`edit_feature {id, fields: {head_depth: …}}`), a plate from the stock series — instead of adding a length.
- The same counterbore depth puts one M4 × 16 through plates of 8 and 10 mm.
- One hole pattern and one screw for the same bought part everywhere (every sensor bracket 2 × M3).
- Holes as standard hole steps that match the screw: `add_feature {type: "hole", standard: "M4", shape:
  "counterbore"}` / `thread: true` — a size change later is one `edit_feature {id, fields: {standard: "M5"}}`.

## 4. Placing them
- Nuts and washers with `library_pair {part, role: "nut"}` or `{part, set: true}` — they take the screw's thread.
- `suggest_fasteners` / `add_fasteners` and `bolt_parts` choose lengths themselves: afterwards read `get_bom` and
  bring odd lengths back into the set.
- A part not in the library: find its maker's model (6.); none to be had: say so, draw a plain stand-in of its outside
  sizes, name it after the part number.

## 5. Hand-over: count and reduce
From `get_bom {mode: "summary"}` report one line:
"Bought parts: 7 kinds, 46 pieces — screws 3 (M4 × 12, M4 × 16, M3 × 8), dowel pins 1, standoffs 1, probes 1,
receptacles 1."
For each group with more than one kind, say whether it can merge ("M4 × 14 → M4 × 16 with the thread 2 mm deeper")
and offer it with `ask_user {question, options, recommended}` — your recommendation first.

## 6. "Use part number X" — find the maker's model
1. `library_search {query: "<part number>"}` (also the series: "DSNU 16"), then the project: `get_bom` / `list_parts`.
2. Not there and you have **WebSearch** (🌐 internet on in the AI settings): search
   `<maker> <part number> STEP download`. Take a **direct file link** (ends in .step / .stp / .igs / .stl / .zip, or a
   maker's download URL) — the maker's own site first (INGUN, igus, Würth, SMC and many others link their STEP files).
3. `fetch_cad {url, part_number, maker, to: "assembly"}` — downloaded, checked, kept in the cache and in the library
   (My parts) with its part number, so it is in `get_bom`. The same part again: `fetch_cad {part_number}` (cache).
4. **A login or a configurator** (TraceParts, CADENAS PARTcommunity, Misumi, Festo, most SMC series — or fetch_cad
   says "a web page, not a CAD file"): give the user the page link and ask them to download the STEP and drag it in.
   Never try to get round a login, a captcha or a configurator.
5. **Internet off** (no WebSearch; fetch_cad refused): ask the user for the file or a link, or draw a stand-in.
6. **Licence**: a maker's model is for use in this design, not to pass on or publish; its source stays with the
   library part — say so when you hand over a STEP export of the assembly.
