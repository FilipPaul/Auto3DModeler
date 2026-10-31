# No way to attach the last recorded session to the AI chat (the 'insert recording' option is missing in the open chat)

- **Kind:** ui
- **Date:** 2026-10-30 11:24:06
- **App version:** 0.9.0 (server started at main @ a059fa4, 2026-10-30; checkout now at c043d7d — restart the app to run it)
- **Reported by:** the AI agent (MCP report_problem)

## What happened

The user recorded their moves with ⏺ and wanted to give the last recorded session to the AI, but the open AI chat window shows no option to insert / attach the recorded session (earlier a message could come with the recording attached).

## What was expected

After a recording stops, the AI chat should always show a clear '📎 Vložit poslední záznam (0:22, 22 událostí)' chip/button above the input (also when the chat was already open while recording, and also later from a list of recent recordings). As a fallback the AI can read it with get_recording — the chat could hint 'AI si záznam umí přečíst sama'.

## Steps

Record with ⏺ in the top bar → stop → open AI chat (it was already open) → no button to insert the recording.
