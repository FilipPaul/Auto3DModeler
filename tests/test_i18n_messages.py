"""Czech for the server's messages: every text the server / kernel sends to the page (issues, refusals as JSON
"error", warnings, notes) is collected from the Python sources and must have a Czech entry in web/js/i18n.js — an
exact text, or a pattern ({} = a value) for a text with values in it. A new message without one fails here.

Run:  python -m unittest discover -s tests -v
      py tests/test_i18n_messages.py   (lists the messages that have no Czech yet)
"""
import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# the sources whose messages reach the page (the MCP server and the AI tool schemas speak to Claude, not the page)
SOURCES = [ROOT / "server.py", *sorted((ROOT / "auto3d").glob("*.py")), *sorted((ROOT / "auto3d" / "modeler").glob("*.py"))]
SKIP_FILES = {"mcp_server.py", "agent_tools.py"}
# functions whose answers go to Claude only (the MCP tools in server.py, report_problem's helpers)
FOR_CLAUDE = re.compile(r"^(tool_|_mcp|_file$|_report_|_shot_file$)")
# errors whose text the server shows (raised, then sent as {"error": str(e)} or as an issue of a step)
ERRORS = {"KernelError", "Unsizable", "KernelFailed", "ValueError", "ImportError_", "TemplateError", "SketchError", "ProjectError",
          "LibraryError", "HistoryError", "AutosaveError", "VersionError", "RuntimeError"}
# small helpers that add an issue: issue(sev, msg), err(msg), self.issue(sev, code, msg); _sized(…, what, unit, why)
HELPERS = {"issue", "err", "_issue", "_sized"}
KEYS = {"message", "error", "warning", "note", "issue"}  # {"error": "…"} and the like
LISTS = {"notes", "warnings"}                               # notes.append("…")
# texts that are not for people (codes, markers in front of a message the page reads)
NOT_TEXT = re.compile(r"^(BLOB_MISSING|MESH_TOO_BIG)\b")
V = "{}"


def _texts(node, names=None):
    """The texts an expression can be: a string, an f-string (values as {}), a + b, a if c else b, {…}[k], or a name
    given a text earlier in the file (`why = "…"; raise KernelError(why)`)."""
    names = names or {}
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        out = [""]
        for v in node.values:
            if isinstance(v, ast.Constant):
                out = [o + v.value for o in out]
                continue
            # {'hole' if a else 'part'}: both words are in the text; {at} that may be "": with a value and without
            alt = _texts(v.value.body, names) + _texts(v.value.orelse, names) if isinstance(v.value, ast.IfExp) else []
            if isinstance(v.value, ast.Name) and "" in names.get(v.value.id, ()):
                alt = [V, ""]
            out = [o + x for o in out for x in (alt or [V])]
        return out
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _texts(node.left, names), _texts(node.right, names)
        return [x + y for x in (a or [V]) for y in (b or [V])] if a or b else []
    if isinstance(node, ast.IfExp):
        return _texts(node.body, names) + _texts(node.orelse, names)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Dict):
        return [s for v in node.value.values for s in _texts(v, names)]
    if isinstance(node, ast.Name):
        return names.get(node.id, [])
    return []


def _sentence(s):
    """A message for people: words in it (not a code like "invalid_value" or a lone value)."""
    s = re.sub(r"\s+", " ", s).strip()
    return s if " " in s.replace(V, "") and re.search(r"[A-Za-z]{2}", s.replace(V, "")) and not NOT_TEXT.match(s) else None


def server_messages():
    """{template: "file:line"} — every message text the server can send to the page, values as {}."""
    out = {}
    for path in SOURCES:
        if path.name in SKIP_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                names.setdefault(node.targets[0].id, []).extend(_texts(node.value))
        claude = {n for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and FOR_CLAUDE.match(f.name)
                  for n in ast.walk(f)}
        for node in ast.walk(tree):
            if node in claude:
                continue
            found = []
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
                if name in ERRORS and node.args:
                    found = _texts(node.args[0], names)
                elif name in HELPERS:
                    found = [s for a in node.args for s in _texts(a, names)]
                elif name == "append" and isinstance(f.value, ast.Name) and f.value.id in LISTS and node.args:
                    found = _texts(node.args[0], names)
            elif isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value in KEYS:
                        found += _texts(v, names)
            for s in found:
                s = _sentence(s)
                if s:
                    out.setdefault(s, f"{path.relative_to(ROOT)}:{node.lineno}")
    return out


# ---------------------------------------------------------------------------- the Czech side (web/js/i18n.js)
_TOKEN = re.compile(r"""//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*|\S""", re.S)


def _js_string(tok):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), tok[1:-1])


def _block(src, start):
    """The tokens of the JS literal that starts at `start` (an object or an array), up to its closing bracket."""
    toks, depth = [], 0
    for m in _TOKEN.finditer(src, src.index(start) + len(start) - 1):
        tok = m.group(0)
        if tok.startswith("//") or tok.startswith("/*"):
            continue
        depth += tok in "{[" and len(tok) == 1
        depth -= tok in "}]" and len(tok) == 1
        toks.append(tok)
        if depth == 0:
            return toks
    raise ValueError(f"{start} does not close")


def czech():
    """(exact English texts with Czech, [(regex, English pattern)]) as i18n.js has them."""
    src = (ROOT / "web" / "js" / "i18n.js").read_text(encoding="utf-8")
    norm = lambda s: re.sub(r"\s+", " ", s).strip()  # noqa: E731
    toks = _block(src, "const CS = {")
    exact = {norm(_js_string(k) if k[0] in "'\"`" else k) for k, c in zip(toks, toks[1:]) if c == ":"}
    toks = _block(src, "const CS_PATTERNS = [")
    pats, row = [], []
    for tok in toks[1:]:
        if tok[0] in "'\"`":
            row.append(_js_string(tok))
        elif tok == "]" and row:
            en = norm(row[0])
            if re.search(r"[A-Za-z]", en.replace(V, "")):  # not the catch-alls ("{} — {}")
                pats.append((re.compile("^" + re.escape(en).replace(re.escape(V), "(.+?)") + "$"), en))
            row = []
    return exact, pats


def missing():
    exact, pats = czech()
    out = {}
    for s, where in server_messages().items():
        if s in exact or f"⚠ {s}" in exact or any(re.match(rx, s) for rx, _ in pats):
            continue
        out[s] = where
    return out


class ServerMessagesInCzech(unittest.TestCase):
    def test_collects_the_messages(self):
        msgs = server_messages()
        self.assertGreater(len(msgs), 300)
        # an f-string's values become {}, both sides of a conditional are texts of their own
        self.assertIn("A draft angle is between 0 and 45°.", msgs)
        self.assertIn("The {} {} {} does not fit here — at most {} {}.", msgs)
        self.assertTrue(any(m.startswith("Choose the rib's sketch") for m in msgs))

    def test_reads_i18n(self):
        exact, pats = czech()
        self.assertIn("Dimensions", exact)          # a bare key
        self.assertIn("Open PDF", exact)            # a quoted one
        self.assertTrue(any(en == "The count is {} … {}." for _, en in pats))

    def test_every_message_has_czech(self):
        left = missing()
        self.assertFalse(left, f"{len(left)} server message(s) without Czech in web/js/i18n.js — add them to CS (exact) "
                               f"or CS_PATTERNS ({{}} = a value):\n" + "\n".join(f"  {w}: {s}" for s, w in sorted(left.items(), key=lambda x: x[1])))


if __name__ == "__main__":
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    left = missing()
    for s, w in sorted(left.items(), key=lambda x: (x[1].split(":")[0], int(x[1].split(":")[1]))):
        print(f"{w}\t{s}")
    print(len(left), "of", len(server_messages()), "without Czech")
