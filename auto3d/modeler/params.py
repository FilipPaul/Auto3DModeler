"""𝑥 Project parameters: named values of the project (`L = 100`, `t = L / 20`) that number fields take as expressions.

The browser is where they are worked out while you edit (web/js/params.js — this is the same in Python, for the
project file and the tests; tests/param_cases.json holds the cases both must agree on). In the project file:
  "parameters": [{"name": "L", "expr": "100"}, {"name": "t", "expr": "L / 20"}]
and a number that uses one keeps its expression beside it, in the object it is in:
  {"id": "F2", "type": "extrude", "d": 50, "expr": {"d": "L/2"}}
  {"id": "d1", "t": "dia", "e": "c1", "v": 8, "expr": {"v": {"x": "D", "k": 0.5}}}   (shown as a radius: value / k)
The number is always the resolved value, so the kernel, exports and older code read numbers as before.

Expressions: numbers (2.5 or 2,5; a unit mm / ° after one is skipped), parameter names, + - * / and brackets — read
by a small parser of our own (no eval).
"""
from __future__ import annotations

import math
import re

NAME_RE = re.compile(r"^[^\W\d]\w*$")
UNITS = {"mm", "deg", "°"}
PLAIN = re.compile(r"^\s*[-+]?(\d+([.,]\d*)?|[.,]\d+)([eE][-+]?\d+)?\s*$")
_NUM = re.compile(r"(\d+([.,]\d*)?|[.,]\d+)([eE][-+]?\d+)?")
_NAME = re.compile(r"[^\W\d]\w*")
OPS = {"+": "+", "-": "-", "−": "-", "*": "*", "×": "*", "·": "*", "/": "/", "÷": "/", "(": "(", ")": ")", "°": "°"}


class ParamError(ValueError):
    """What went wrong in an expression; code: empty | char | end | paren | extra | unknown | cycle | zero | name | bad."""

    def __init__(self, code, text):
        super().__init__(text)
        self.code = code


def is_plain(s) -> bool:
    return bool(PLAIN.match(str(s if s is not None else "")))


def _tokens(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
            continue
        m = _NUM.match(s, i)
        if m:
            out.append(("num", float(m.group(0).replace(",", ".")), i))
            i = m.end()
            continue
        m = _NAME.match(s, i)
        if m:
            out.append(("name", m.group(0), i))
            i = m.end()
            continue
        if c not in OPS:
            raise ParamError("char", f"Cannot read “{c}” in “{s.strip()}”.")
        out.append((OPS[c], None, i))
        i += 1
    return out


def parse(text):
    """text -> a tree: ("num", v) | ("ref", name) | ("neg", a) | (op, a, b). Raises ParamError."""
    src = re.sub(r"^=\s*", "", str(text if text is not None else "").strip())
    if not src:
        raise ParamError("empty", "Type a value or an expression.")
    tk = _tokens(src)
    pos = [0]

    def peek():
        return tk[pos[0]] if pos[0] < len(tk) else None

    def take():
        t = peek()
        pos[0] += 1
        return t

    def unit(node):
        n = peek()
        if n and (n[0] == "°" or (n[0] == "name" and n[1] in UNITS)):
            pos[0] += 1
        return node

    def primary():
        n = take()
        if n is None:
            raise ParamError("end", f"The expression “{src}” is not finished.")
        if n[0] == "num":
            return unit(("num", n[1]))
        if n[0] == "name":
            return unit(("ref", n[1]))
        if n[0] == "(":
            e = total()
            if (peek() or ("",))[0] != ")":
                raise ParamError("paren", f"A bracket is not closed in “{src}”.")
            pos[0] += 1
            return unit(e)
        if n[0] in "+-":
            a = primary()
            return ("neg", a) if n[0] == "-" else a
        raise ParamError("char", f"Cannot read “{n[0]}” in “{src}”.")

    def product():
        a = primary()
        while (peek() or ("",))[0] in ("*", "/"):
            a = (take()[0], a, primary())
        return a

    def total():
        a = product()
        while (peek() or ("",))[0] in ("+", "-"):
            a = (take()[0], a, product())
        return a

    tree = total()
    if pos[0] < len(tk):
        t = tk[pos[0]]
        raise ParamError("paren" if t[0] == ")" else "extra", f"Something extra after the expression: “{src[t[2]:]}”.")
    return tree


def refs(tree, out=None):
    out = set() if out is None else out
    if tree[0] == "ref":
        out.add(tree[1])
    elif tree[0] != "num":
        for x in tree[1:]:
            refs(x, out)
    return out


def calc(tree, value):
    op = tree[0]
    if op == "num":
        return tree[1]
    if op == "ref":
        return value(tree[1])
    if op == "neg":
        return -calc(tree[1], value)
    x, y = calc(tree[1], value), calc(tree[2], value)
    if op == "+":
        return x + y
    if op == "-":
        return x - y
    if op == "*":
        return x * y
    if y == 0:
        raise ParamError("zero", "Division by zero.")
    return x / y


def _unknown(name):
    return ParamError("unknown", f"There is no parameter “{name}” — type {name} = 100 to make it.")


def evaluate_all(params):
    """[{name, expr}] -> (values {name: number}, errors {name: ParamError}); a parameter that refers to one with an
    error, or round in a circle, has an error too."""
    by = {p["name"]: p for p in params or [] if isinstance(p, dict) and p.get("name")}
    values, errors, state = {}, {}, {}

    def visit(name, path):
        if state.get(name) == "done":
            if name in errors:
                raise ParamError("bad", f"The parameter “{name}” has an error: {errors[name]}")
            return values[name]
        if state.get(name) == "busy":
            loop = path[path.index(name):] + [name]
            raise ParamError("cycle", f"The parameters refer to each other in a circle: {' → '.join(loop)}.")
        if name not in by:
            raise _unknown(name)
        state[name] = "busy"
        try:
            v = calc(parse(by[name].get("expr", "")), lambda n: visit(n, path + [name]))
            if not math.isfinite(v):
                raise ParamError("zero", "Division by zero.")
            values[name] = v
        except ParamError as e:
            errors[name] = e
            state[name] = "done"
            raise
        state[name] = "done"
        return v

    for name in by:
        try:
            visit(name, [])
        except ParamError:
            pass
    return values, errors


def eval_text(expr, values):
    """An expression's value with these parameter values; raises ParamError."""
    def value(n):
        if n not in values:
            raise _unknown(n)
        return values[n]
    v = calc(parse(expr), value)
    if not math.isfinite(v):
        raise ParamError("zero", "Division by zero.")
    return v


def value_of(expr, values):
    """An expression's value with these values (None: it cannot be worked out)."""
    try:
        return eval_text(expr, values)
    except ParamError:
        return None


def _entry(e):
    return (e, 1.0) if isinstance(e, str) else ((e or {}).get("x", ""), float((e or {}).get("k") or 1))


def resolve(root, values):
    """Put the values in: every dict in root (deep) with an "expr" gets its numbers worked out again (in place).
    -> how many numbers changed (an expression that cannot be worked out keeps its number)."""
    n = 0

    def walk(o, depth):
        nonlocal n
        if depth > 12:
            return
        if isinstance(o, list):
            if o and not isinstance(o[0], (int, float)):
                for x in o:
                    walk(x, depth + 1)
            return
        if not isinstance(o, dict):
            return
        ex = o.get("expr")
        if isinstance(ex, dict):
            for k, e in ex.items():
                text, scale = _entry(e)
                v = value_of(text, values)
                if v is None:
                    continue
                to = round(v / scale, 9)
                if o.get(k) != to:
                    o[k] = to
                    n += 1
        for k, x in o.items():
            if k != "expr" and isinstance(x, (dict, list)):
                walk(x, depth + 1)

    walk(root, 0)
    return n


def apply_project(proj):
    """A project file's numbers made to agree with its parameters (a file edited by hand, or saved half way):
    the model parts' steps and the assemblies' joints. -> how many numbers changed."""
    values, _ = evaluate_all(proj.get("parameters") or [])
    n = 0
    for p in proj.get("parts") or []:
        if isinstance(p, dict) and p.get("kind") in ("model", "assembly"):
            n += resolve(p.get(p["kind"]) or {}, values)
    return n
