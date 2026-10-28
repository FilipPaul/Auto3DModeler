# Auto3DModeler — working rules

Read `docs/ARCHITECTURE-modeler.md` (the plan and its Progress section) before starting work. The agents in
`.claude/agents/` (architect, programmer, tester, ui-designer) follow the same rules.

## Workflow
- Keep going through the roadmap (Progress → "Next") on your own; do not ask whether to continue. Ask only for
  real decisions (installing something large, a choice with no sensible default).
- Intuitive first: a tool that needs many inputs (more than ~2) is deferred. Every new UI string gets a Czech
  entry in `web/js/i18n.js`.

## Commits — commit each reached goal
- **Commit as soon as a goal is reached**: a milestone, a feature, a tool, a bug fix, a docs / rules update.
  One goal per commit; do not pile several goals into one commit or leave finished work uncommitted.
- A goal counts as reached when its tests pass:
  - `py -m unittest discover -s tests` (all OK);
  - the browser tests that cover it (`tools/e2e_*.py` <url> <out dir>; restart your test server after backend
    changes — the kernel worker keeps old code; see "Several agents at once" for which port is yours).
  Never commit with failing tests; say what fails instead.
- In the same commit: the tests for it, README / `docs/ARCHITECTURE-modeler.md` Progress, the tester's list in
  `.claude/agents/tester.md` when a new e2e test is added.
- Stage the files by name (`git add <paths>`), not `git add -A`; check `git status` for strays (screenshots,
  `*.a3d.json`, temp scripts) first. Test output goes to the scratchpad, not the repo. Leave the untracked
  `RealSWReports/*.md` (the app's AI writes them) alone.
- Message: a short imperative subject (≤ 72 chars, e.g. "Add ⁂ Pattern feature: repeat steps in a row or
  around an axis"), a blank line, then what changed and how it was verified. End with the attribution line
  the session asks for (today: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
- Commit on the branch the owner works on (`main`) and **push after each commit** (the owner asked for it,
  2026-10-28). Never force-push, rebase or amend.

## Several agents at once
The main session hands development jobs to the agents in `.claude/agents/`, running in the background, so the
owner can keep talking to it. Several may work in this one working tree at the same time:
- **Your own test server.** The main session's is `--port 5199`; an agent starts its own on another port (the
  one its task names, else 5198 / 5197 / 5196 …) with its own data folder:
  `A3D_DATA=<your scratchpad>/testdata py server.py --port <port> --no-browser` (in the background). The `5199`
  in the examples in `.claude/agents/*.md` means *your* port. Never stop a server you did not start.
- **Only your own changes.** Before committing, `git status` and `git diff` — stage only the files (and hunks)
  your goal changed; never revert, reformat or "fix" someone else's uncommitted work. If a file you need is
  being changed by another job, say so in your report instead of overwriting it.
- **Never stage into the shared index** (`.git/index`: no `git add`, `git update-index`, `git apply --cached`)
  — another agent's `git commit` would take your files with it (this happened: 73bdbff). Commit through a
  **private index** instead:
  `export GIT_INDEX_FILE=<your scratchpad>/idx-<job>; git read-tree HEAD`, put your versions of your files in it
  (whole files that are only yours: `git update-index --add <path>` — with that GIT_INDEX_FILE set; a shared file:
  `git show HEAD:<file>` plus only your edits, written to a temp file and added with
  `git update-index --add --cacheinfo 100644,$(git hash-object -w <temp file>),<file>`), read
  `git diff --cached` (same GIT_INDEX_FILE), `git commit`, then `unset GIT_INDEX_FILE` and
  `git reset -q -- <your paths>` so the shared index matches the new HEAD for your files. Never `git commit -a`.
- **HEAD must pass the unit tests** after your commit: check in a clean worktree of HEAD
  (`git worktree add <scratchpad>/wt HEAD`), not only in the shared tree with others' half-done work.
- **Small goals, committed at once**, so others build on them; `git pull` is not needed (one local clone).
- **Report back** in a few lines: what works, what was left out, the commit hashes, test results with numbers.

## Environment
- Windows; Python is `py`. Set `PYTHONIOENCODING=utf-8` for non-ASCII output.
- Bash heredocs break on quotes / backslashes — write patch scripts to a file and run them.
