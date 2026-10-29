# Distributing Auto3DModeler (Windows)

For the owner (a developer): how to build the program a customer can run on Windows 10 / 11 x64 **without Python**,
what the customer gets, where their data lives, the AI, updates and code signing. The customer's own short guide (in
Czech) is at the end — copy it into an e-mail or next to the download.

## What the app needs at run time

| What | Where it comes from in the build |
| --- | --- |
| Python 3.13 + the packages of `requirements.txt` and `requirements-modeler.txt` (Flask, OpenCV, PyMuPDF, shapely, ezdxf, cascadio, the OpenCASCADE kernel `cadquery-ocp-novtk`, the sketch solver `planegcs`, openpyxl) | PyInstaller collects them into `_internal/`; the versions are pinned in `tools/build/constraints.txt` |
| `server.py`, `auto3d/` | compiled into the exe's archive |
| `web/` (the page, its fonts and vendored three.js), `library/` (the parts library), `agent_plugin/` (the AI's skills), `demos/` (the 🎬 demo projects, read-only: opened as a copy), `initial draft.pdf` (the sample drawing) | data files in `_internal/`; smoke.py checks `/api/demos` lists and opens them |
| The CAD kernel's processes (`auto3d/modeler/worker.py`, multiprocessing "spawn") | the same exe started again: `tools/build/Auto3DModeler.py` calls `multiprocessing.freeze_support()` first |
| The AI chat's MCP server (`auto3d/mcp_server.py`) | the same exe: `Auto3DModeler.exe --mcp-server --url …` (`auto3d/agent.py` uses it when built) |
| The user's data | `%LOCALAPPDATA%\Auto3DModeler` — never the install folder (see below) |
| A window | Microsoft Edge (on every Windows 10 / 11) as an app window, else the default browser |
| AI: Claude Code + a Claude account or an API key | **not** in the build — the customer's own (see "AI") |

Left out of the build: `samples/` (57 MB of test files), `tests/`, `tools/`, `RealSWReports/`. The ODA File Converter
(DWG import) stays an optional separate install, as before.

## Building

On a Windows x64 machine with Python 3.13 (`py`) and internet access:

```
py tools/build/build.py               # a fresh build/venv (≈ 3 min), PyInstaller (≈ 1 min), zip, smoke test
py tools/build/build.py --reuse-venv  # keep build/venv: ≈ 1.5 min
```

It makes a clean venv (`build/venv`) from `requirements.txt`, `requirements-modeler.txt` and
`tools/build/requirements-build.txt` (PyInstaller, pystray for the tray icon), pinned by `tools/build/constraints.txt`;
writes `build/stage/BUILD.json` (the commit — the built app has no git; `/api/version` and the AI's problem reports show
it) and the icon; runs `tools/build/auto3d.spec`; zips the result; builds the installer when Inno Setup is installed;
and runs `tools/build/smoke.py` on the result (on port 5194, its own data folder in `build/smoke-data`): the server
answers, `/api/kernel` reports the OCP kernel and the sketch solver, a 40 × 20 × 10 block is built by a kernel process
(8000 mm³) and exported as STEP.

Output (all ignored by git):

| File | What |
| --- | --- |
| `dist/Auto3DModeler/` | the program: `Auto3DModeler.exe` + `_internal/` (≈ 445 MB) |
| `dist/Auto3DModeler-<version>-win64-portable.zip` | that folder zipped (≈ 160 MB) — the "portable" variant |
| `dist/Auto3DModeler-<version>-setup.exe` | the installer (only with Inno Setup 6) |

The version is `VERSION` in `auto3d/version.py` — raise it before a release; the zip, the installer and the
uninstaller's entry take it from there.

**Testing a build by hand** (your own port and data folder — never the customer's):

```
py tools/build/smoke.py dist\Auto3DModeler\Auto3DModeler.exe %TEMP%\a3d-test 5194 --keep
PYTHONIOENCODING=utf-8 py tools/e2e_model_features.py http://127.0.0.1:5194 %TEMP%\e2e
taskkill /T /F /PID <the pid it printed>
```

Checked for this build (2026-10-29): the smoke test, `tools/e2e_model_features.py`, `tools/e2e_exchange_formats.py`
and a real chat (`tools/e2e_chat.py`: Claude made a 30 × 20 × 5 mm plate through the exe's own MCP server) against
the built exe; a second start only opening the window; closing the window quitting the app (its kernel processes
too).

### The installer (Inno Setup)

`tools/build/installer.iss` — needs [Inno Setup 6](https://jrsoftware.org/isinfo.php) (free, ≈ 5 MB; a separate
install on the build machine, not on the customer's). With it installed, `build.py` runs it by itself; by hand:

```
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" /DAppVersion=0.9.0 /DSourceDir=%CD%\dist\Auto3DModeler /O%CD%\dist tools\build\installer.iss
```

What it does: installs **per user without admin rights** (`%LOCALAPPDATA%\Programs\Auto3DModeler`; "for all users" can
be picked in its first dialog — then admin and Program Files), a Start menu entry, an optional desktop icon
(unticked), the uninstaller (Settings → Apps), Czech and English wizard. An update replaces the program folder and
closes a running copy first. The AppId in the script ties updates and the uninstaller together — never change it.

Without Inno Setup the zip is the deliverable: the customer unpacks it anywhere (e.g. `Documents\Auto3DModeler`) and
runs `Auto3DModeler.exe`. Same program, no Start menu entry or uninstaller.

## What the customer's program does

- **Auto3DModeler.exe** starts the server on 127.0.0.1 (port 5173, or a free one when it is taken; only this
  computer can reach it) and opens the app in **its own window** (Edge `--app`: no tabs, no address bar, its own
  profile in the data folder). No console window.
- **One copy**: a second start (or a click on the Start menu entry while it runs) only opens another window of the
  running one — a named mutex per data folder + `instance.json` with its address. That window starts on the start
  screen with a project of its own (*Continue where you left off* offers the last project that is **not** open in
  another window — no second copy of the same project unless picked in 🕘 Recent projects, where it is marked *open
  in another window*); each window's title is its project's name. Each window's ✨ AI chat is its own: the AI works in
  the window it is asked in, never in another (a window closed: its chat's calls fail, saying so). In a window,
  **📄 New project** (Open ▾, Ctrl+Alt+N) starts an empty project there, the previous one kept in 🕘 Recent projects;
  **⧉ New project in a new window** (or Ctrl+click on 📄) opens one side by side.
- **Quitting**: closing the app window quits the app (the server, the CAD kernel processes, the chat's Claude Code).
  The **tray icon** (a blue cube) has *Open*, *Open in the browser*, *Logs* and *Quit* (in Czech on a Czech Windows) —
  for when the window was the default browser's
  (no Edge), or the user wants a second window.
- **Start-up problems** show a message box pointing at the log.
- Command line (support, tests): `--port N` (or `A3D_PORT`), `--no-browser`, `--browser` (the default browser instead
  of the app window), `--no-tray`; `A3D_DATA=<folder>` moves the data folder.

Start: the server answers 0.3 – 1.2 s after the start on the build machine (warm disk cache); the first start after
an install takes longer while Windows Defender scans the new files (not measured on a clean machine).

## Where the data lives

`%LOCALAPPDATA%\Auto3DModeler` (e.g. `C:\Users\<name>\AppData\Local\Auto3DModeler`), per Windows user:

| Folder / file | What |
| --- | --- |
| `projects\` | autosaved projects |
| `library\` | the user's own library parts |
| `history\` | the project after each AI turn |
| `agent\` | the AI chat's working folder and attached photos |
| `ai\key.bin` | the Anthropic API key, when one was entered (DPAPI-encrypted for this Windows user) |
| `imports\` | imported 3D files (by hash) |
| `RealSWReports\` | the AI's problem reports (from a checkout they go to the repo's folder) |
| `printers.json`, title-block templates | settings |
| `logs\auto3d.log` (+ `auto3d.1.log`) | the log (moved aside at the next start past 5 MB) |
| `window\` | the app window's Edge profile (the page's own settings: language, layout) |
| `instance.json` | the running copy's address (gone when it quits) |

Plus `%USERPROFILE%\.auto3d\blobs` (big imported files the model refers to; `AUTO3D_BLOBS` moves it). Neither is
touched by an uninstall or an update; delete `%LOCALAPPDATA%\Auto3DModeler` to remove everything.

From a checkout (`py server.py`) nothing changes: the data stays in the repo's `data/` (or `A3D_DATA`).
`py -m auto3d.launcher` runs the desktop start from a checkout too.

## AI

The ✨ AI chat runs the customer's own **Claude Code** (`auto3d/agent.py`), which talks to Claude with the customer's
own sign-in; the app hands it only its part tools (its MCP server — the exe itself in the build). Nothing of it is in
the build, and the app starts and works fully without it.

The customer needs:
1. **Claude Code** — the native installer needs no Node.js and no admin rights: in PowerShell
   `irm https://claude.ai/install.ps1 | iex` (see claude.com/claude-code). The app finds it on PATH, in
   `%USERPROFILE%\.local\bin`, or in a VS Code / Cursor extension; `AUTO3D_CLAUDE` points at another one.
2. **A Claude account** with a Pro or Max subscription, **or** an Anthropic API key (console.anthropic.com, pay per
   use).

**All of it can be set up later, while the app runs** (`auto3d/ai_access.py`, the ✨ AI panel): when the AI is not
ready the panel shows *Set up the AI assistant* (in Czech: *Nastavení AI asistenta*) instead of the chat, in one of
these states (`GET /api/ai/access`):

| State | The screen |
| --- | --- |
| `no_claude` — Claude Code not found | the install command and a link; **Check again** (no restart) |
| `signed_out` — no sign-in, no key | **Sign in with Claude** (`POST /api/ai/login`: Claude Code's own `claude auth login` in a window of its own — a browser page; the screen asks again every 2 s and switches to the chat once signed in), a register link (claude.ai); **an API key** field + a link to console.anthropic.com |
| `invalid` — the kept key was refused | "The API key was refused…" + the same two ways |
| `ok` — a key or a sign-in works | the chat; **🔑 Access** shows who is connected and **Sign out / change the key** |

- An API key (`POST /api/ai/key`) is checked with Anthropic first (`GET https://api.anthropic.com/v1/models`): refused
  -> "Anthropic refused this key", nothing kept; no connection -> kept with a warning. It is stored per Windows user in
  `%LOCALAPPDATA%\Auto3DModeler\ai\key.bin`, encrypted with **DPAPI** (only this Windows user can read it back;
  never in the install folder, never logged) and given only to the chat's Claude Code as `ANTHROPIC_API_KEY`.
- A Claude account sign-in stays Claude Code's own (in `%USERPROFILE%\.claude`); the app only asks
  `claude auth status`. *Sign out* there signs Claude Code out on the whole computer (the app asks first).
- A chat turn that Claude refuses for the access (a revoked / expired key, signed out) marks the key invalid and brings
  the set-up screen back with a clear message; the next message starts a fresh Claude Code with the new access.
- Tests: `tests/test_ai_access.py` (the key kept / read / forgotten, DPAPI, the check refused / offline / ok, the
  states, a refused chat turn, the routes), `tools/e2e_ai_access.py` (the screen with no sign-in, a fake key refused,
  in Czech, a 3D model still builds — its server started with `CLAUDE_CONFIG_DIR=<an empty dir>`).

## Updating

Build with a higher `VERSION`, send the new setup (it installs over the old one; the data stays) or the new zip
(replace the old folder; the data stays). There is no automatic update check.

## Code signing

The exe and the installer are **unsigned**: Windows SmartScreen shows "Windows protected your PC" for a downloaded
file until it has a reputation — the customer clicks *More info → Run anyway* (and a zip from the internet may need
*Properties → Unblock* before unpacking). Some antivirus programs also flag unsigned PyInstaller programs.

To sign (the owner's decision — it costs money and an identity check):
- **Azure Trusted Signing** (Microsoft; about USD 10 / month): an organisation with a verifiable history; signs from
  the command line / CI without a hardware token. Cheapest and simplest when the company qualifies.
- **An OV code-signing certificate** from a CA (Sectigo, DigiCert, Certum … about EUR 200 – 500 / year). Since 2023
  the private key must live on a hardware token or a cloud HSM. Certum's "open source" / small-business offers are
  cheaper.
- (EV certificates no longer skip SmartScreen's reputation building, since 2024 — not worth the extra cost here.)

Sign both files after the build, with a timestamp so the signature outlives the certificate:

```
signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /a dist\Auto3DModeler\Auto3DModeler.exe
signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /a dist\Auto3DModeler-0.9.0-setup.exe
```

(the exe before zipping / running ISCC; Inno Setup can also call signtool itself through `SignTool=` in the script).

## Files

`tools/build/build.py` (the build), `tools/build/auto3d.spec` (PyInstaller), `tools/build/Auto3DModeler.py` (the exe's
entry), `tools/build/installer.iss` (Inno Setup), `tools/build/smoke.py` (the smoke test), `tools/build/icon.py`,
`tools/build/requirements-build.txt`, `tools/build/constraints.txt`; `auto3d/launcher.py` (the desktop start: data
folder, port, one copy, the window, tray, logs; `tests/test_launcher.py`).

---

## Instalace (pro zákazníka)

**Co potřebujete:** Windows 10 nebo 11 (64bitové). Nic dalšího se instalovat nemusí — Python ani jiné programy ne.

**Instalace**
1. Spusťte `Auto3DModeler-<verze>-setup.exe`.
   - Pokud Windows ukáže „Systém Windows ochránil váš počítač“, klikněte na **Další informace → Přesto spustit**
     (program zatím není digitálně podepsaný).
2. Projděte průvodce (instaluje se jen pro vás, bez práv správce). Ikonu na ploše si můžete zaškrtnout.
3. Program spustíte z nabídky Start: **Auto3DModeler**.

*Varianta bez instalace (zip):* rozbalte `Auto3DModeler-<verze>-win64-portable.zip` do libovolné složky (např.
Dokumenty) a spusťte `Auto3DModeler\Auto3DModeler.exe`. Pokud Windows soubor zip blokuje: pravé tlačítko →
Vlastnosti → **Odblokovat**, pak rozbalit.

**Používání**
- Program se otevře ve vlastním okně. Zavřením okna se program ukončí.
- Ikona (modrá kostka) vedle hodin: **Otevřít** (okno), **Otevřít v prohlížeči**, **Záznamy (logy)** (složka pro
  podporu), **Ukončit**.
- Druhé spuštění jen otevře okno už běžícího programu.

**Vaše data** (projekty, knihovna dílů, nastavení) jsou v `%LOCALAPPDATA%\Auto3DModeler` (vložte do adresního řádku
Průzkumníka). Odinstalace ani aktualizace je nemaže.

**AI asistent (✨ AI)** je volitelný — zbytek programu funguje i bez něj. Nastavit ho můžete kdykoli, i později, bez
restartu: klikněte na **✨ AI** a postupujte podle obrazovky *Nastavení AI asistenta*:
1. Pokud chybí **Claude Code**, obrazovka ukáže příkaz k instalaci (do PowerShellu, bez práv správce); pak
   **Zkontrolovat znovu**.
2. Pak buď **Přihlásit se přes Claude** (účet Claude s předplatným Pro nebo Max; registrace na claude.ai), nebo vložte
   **klíč API** z console.anthropic.com. Klíč se uloží šifrovaně jen pro vašeho uživatele Windows.
3. Odhlášení nebo změna klíče: v chatu tlačítko **🔑 Přístup**.

**Aktualizace:** spusťte instalátor nové verze — nainstaluje se přes starou, data zůstanou.

**Odinstalace:** Nastavení → Aplikace → Auto3DModeler → Odinstalovat. Chcete-li smazat i svá data, smažte složku
`%LOCALAPPDATA%\Auto3DModeler`.

**Když něco nefunguje:** pošlete nám soubor `%LOCALAPPDATA%\Auto3DModeler\logs\auto3d.log`.
