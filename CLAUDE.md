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
  - the browser tests that cover it (`tools/e2e_*.py`; restart `py server.py --port 5199 --no-browser`
    after backend changes — the kernel worker keeps old code).
  Never commit with failing tests; say what fails instead.
- In the same commit: the tests for it, README / `docs/ARCHITECTURE-modeler.md` Progress, the tester's list in
  `.claude/agents/tester.md` when a new e2e test is added.
- Stage the files by name (`git add <paths>`), not `git add -A`; check `git status` for strays (screenshots,
  `*.a3d.json`, temp scripts) first. Test output goes to the scratchpad, not the repo.
- Message: a short imperative subject (≤ 72 chars, e.g. "Add ⁂ Pattern feature: repeat steps in a row or
  around an axis"), a blank line, then what changed and how it was verified. End with the attribution line
  the session asks for.
- Commit on the branch the owner works on (`main`); never push, rebase or amend unless asked.

## Environment
- Windows; Python is `py`. Set `PYTHONIOENCODING=utf-8` for non-ASCII output.
- Bash heredocs break on quotes / backslashes — write patch scripts to a file and run them.
