# Tool errors 2026-11-01

- **Kind:** tool errors
- **Date:** 2026-11-01
- **App version:** 0.9.0 (server started at main @ 6416133, 2026-11-01; checkout now at 13ab770 — restart the app to run it)
- **Reported by:** the app, on its own (every AI tool call that failed; the same tool and message counted)
- **Errors:** 4 different, 4 calls

## 1. find_refs — ×1

- **Error:** find_refs: an assembly is on screen — open_part the part to change it, or use get_assembly / insert_part / snap_faces / place_part.
- **When:** 01:42:03
- **App version:** 0.9.0 (main @ 6416133, 2026-11-01)
- **Where:** workspace assembly · part Plynová vzpěra 175N_oa_6
- **Conversation:** 20261101-014149-799334
- **Arguments:** `{"kind": "face", "of_step": "F1"}`

## 2. set_travel — ×1

- **Error:** I45/I4 is inside a sub-assembly: move_free moves it here; its limits and locks are its own assembly's (open_part it).
- **When:** 01:50:25
- **App version:** 0.9.0 (server started at main @ 6416133, 2026-11-01; checkout now at 196a87b — restart the app to run it)
- **Where:** workspace assembly · part Sestava brány
- **Conversation:** 20261101-014149-799334
- **Arguments:** `{"part": "I45/I4", "motion": 0, "min": -165, "max": -75}`

## 3. drive_mechanism — ×1

- **Error:** Building took longer than 120 s and was stopped.
- **When:** 01:52:49
- **App version:** 0.9.0 (server started at main @ 6416133, 2026-11-01; checkout now at 196a87b — restart the app to run it)
- **Where:** workspace assembly · part Sestava ICT M1556
- **Conversation:** 20261101-014149-799334
- **Arguments:** `{"mechanism": "M1", "to": -165, "collisions": true}`

## 4. drive_mechanism — ×1

- **Error:** I5/I45/I4 cannot move inside I5 — get_assembly lists what can as `inner` of a sub-assembly.
- **When:** 01:56:36
- **Where:** workspace assembly · part Sestava ICT M1556
- **Conversation:** 20261101-014149-799334
- **Arguments:** `{"mechanism": "I5", "driver": {"part": "I5/I45/I4", "motion": 0}, "to": -120}`
