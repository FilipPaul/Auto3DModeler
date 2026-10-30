"""No pop-up windows from the browser: every question is asked inside the app (the owner's firm rule). The page's
sources (web/js/**/*.js) must not call the browser's own confirm / alert / prompt — as a bare call, through
window. / globalThis. / self., or as window[...] — nor ask on leaving the page (beforeunload). Ask in the page
instead: choose.js choose() / ask() / confirmIn(), a bar in the view (assembly.js askBreak), or do it and offer ↶ in
a toast. Comment lines are not read.

Run:  py -m unittest discover -s tests -p "test_no_native_dialogs.py" -v
"""
import re
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "web" / "js"

BAD = [
    (re.compile(r"(?<![.\w$])(confirm|alert|prompt)\s*\("), "the browser's {0}() pop-up"),
    (re.compile(r"\b(window|globalThis|self|top|parent)\s*\.\s*(confirm|alert|prompt)\b"), "the browser's {1}() pop-up"),
    (re.compile(r"\bwindow\s*\["), "window[...] (a pop-up reached by name?)"),
    (re.compile(r"beforeunload"), "a question on leaving the page (beforeunload)"),
]


def offenders():
    """-> ["file:line: what — the line"] for every native dialog call in the page's sources."""
    found = []
    for path in sorted(JS.rglob("*.js")):
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.strip()
            if code.startswith(("//", "*", "/*")):
                continue
            code = re.sub(r"\s//\s.*$", "", code)  # (a comment after the code)
            for rx, what in BAD:
                m = rx.search(code)
                if m:
                    found.append(f"{path.relative_to(JS.parent.parent).as_posix()}:{no}: {what.format(*m.groups())} — {line.strip()[:140]}")
    return found


class NoNativeDialogs(unittest.TestCase):
    def test_no_browser_popups(self):
        bad = offenders()
        self.assertEqual(bad, [], "native browser dialogs found (ask inside the app: choose.js confirmIn / choose / ask):\n" + "\n".join(bad))

    def test_the_scan_finds_them(self):
        # the patterns themselves: what they must catch, and what they must leave alone
        catch = ["if (!confirm('x')) return;", "window.confirm(t('x'))", "alert(msg)", "const v = prompt('Name?');",
                 "window['confirm']('x')", "addEventListener('beforeunload', f)", "globalThis.alert('x')"]
        leave = ["await confirmIn('x')", "this.confirm()", "buildPrompt(x)", "el.dataset.alert = 1", "{ cls: 'confirm' }"]
        hit = lambda s: any(rx.search(s) for rx, _ in BAD)
        self.assertEqual([s for s in catch if not hit(s)], [])
        self.assertEqual([s for s in leave if hit(s)], [])


if __name__ == "__main__":
    unittest.main()
