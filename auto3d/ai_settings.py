"""✨ AI settings: how the chat's AI should work (the design profile, manufacturing, when to ask, answer length,
the design rules and modes) — chosen in the chat's ✨ panel (web/js/aisettings.js), kept per project.

The AI gets them as one short line before a user message (`settings_line`, under ~100 tokens), sent only when it
changed since the last message of the conversation. Tags in a message (#uc, #cnc …) change them for that one message
(`parse_tags`): they are taken out of the text the AI sees. 🌐 Search the internet is also kept for the server
(`save_internet`: <data>/ai/settings.json, read when the chat's Claude Code starts — auto3d.fetchcad.internet_on).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PROFILES = {  # what picking a profile sets (the rest — asking, answers, modes, internet — stays)
    "automation": {"make": ["cnc"], "standard": True, "dfm": True, "dfa": True, "review": True},
    "print": {"make": ["print"], "standard": True, "dfm": True, "dfa": True, "review": True},
    "deco": {"make": ["print"], "standard": False, "dfm": False, "dfa": False, "review": False},
}
DEFAULTS = {"profile": "automation", **PROFILES["automation"], "ask": "key", "answers": "short",
            "teach": False, "bugs": False, "internet": True, "lean": False}
MAKES = ("cnc", "print", "laser")
CHOICES = {"profile": (*PROFILES, "custom"), "ask": ("key", "all", "none"), "answers": ("short", "normal", "explain")}
FLAGS = ("standard", "dfm", "dfa", "review", "teach", "bugs", "internet", "lean")

# the tags a message may carry (also typed with Czech letters): what each changes for that message
TAGS = {
    "uc": {"teach": True},
    "chyby": {"bugs": True},
    "kontrola": {"review": True},
    "rychle": {"lean": True, "review": False, "answers": "short"},
    "cnc": {"make": ["cnc"]},
    "tisk": {"make": ["print"]},
    "bez-otazek": {"ask": "none"},
}
ALIASES = {"uč": "uc", "rychlé": "rychle", "bez-otázek": "bez-otazek"}
TAG_RE = re.compile(r"(?<![\w#])#([\w-]+)(?![\w-])", re.U)

WORDS = {  # the line's words (Czech, short: the AI reads them; the routing in SYSTEM_PROMPT names them)
    "profile": {"automation": "automatizace", "print": "tisk", "deco": "dekorace", "custom": "vlastní"},
    "make": {"cnc": "CNC", "print": "3D-tisk", "laser": "laser"},
    "ask": {"key": "klíčové", "all": "vše", "none": "neptat"},
    "answers": {"short": "stručně", "normal": "normálně", "explain": "vysvětlit"},
}


def clean(settings) -> dict:
    """Settings from the page / a project file -> a complete, valid dict (unknown or wrong values: the defaults)."""
    s = dict(DEFAULTS)
    if not isinstance(settings, dict):
        return s
    for k, allowed in CHOICES.items():
        if settings.get(k) in allowed:
            s[k] = settings[k]
    if isinstance(settings.get("make"), list):
        s["make"] = [m for m in MAKES if m in settings["make"]]
    for k in FLAGS:
        if isinstance(settings.get(k), bool):
            s[k] = settings[k]
    return s


def parse_tags(text: str) -> tuple[str, list[str]]:
    """"Make a bracket #uc #cnc" -> ("Make a bracket", ["uc", "cnc"]): the known tags taken out (in order, once
    each); other #words (#5, #anything) stay in the text."""
    tags = []

    def take(m):
        name = m.group(1).lower()
        name = ALIASES.get(name, name)
        if name not in TAGS:
            return m.group(0)
        if name not in tags:
            tags.append(name)
        return ""

    out = TAG_RE.sub(take, text or "")
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = "\n".join(line.strip() for line in out.split("\n")).strip()
    return out, tags


def apply_tags(settings: dict, tags) -> dict:
    """The settings for one message: the tags' changes over them."""
    s = dict(settings)
    for tag in tags:
        s.update(TAGS.get(tag, {}))
    return s


def rules(s: dict) -> list[str]:
    """The design rules on -> the skill (or rule) names the AI loads."""
    out = []
    if s["standard"]:
        out.append("standard-parts")
    if s["dfm"]:
        out += [{"cnc": "machined-part", "print": "print-functional", "laser": "easy-manufacture"}[m] for m in s["make"]] or ["easy-manufacture"]
    if s["dfa"]:
        out.append("easy-assembly")
    if s["review"]:
        out.append("design-review")
    return list(dict.fromkeys(out))


def settings_line(settings, tags=()) -> str:
    """The settings (and a message's tags) as the line the AI gets, e.g.
    [Nastavení: profil=automatizace; výroba=CNC; ptát=klíčové; odpovědi=stručně; zásady=standard-parts,machined-part,
    easy-assembly,design-review; režimy=-; internet=ano]"""
    s = apply_tags(clean(settings), tags)
    modes = [m for k, m in (("teach", "teach-me"), ("bugs", "bug-hunter"), ("lean", "lean")) if s[k]]
    parts = [f"profil={WORDS['profile'][s['profile']]}",
             f"výroba={','.join(WORDS['make'][m] for m in s['make']) or '-'}",
             f"ptát={WORDS['ask'][s['ask']]}",
             f"odpovědi={WORDS['answers'][s['answers']]}",
             f"zásady={','.join(rules(s)) or '-'}",
             f"režimy={','.join(modes) or '-'}",
             f"internet={'ano' if s['internet'] else 'ne'}"]
    return f"[Nastavení: {'; '.join(parts)}]"


def lean(settings, tags=()) -> bool:
    """⚡ Lean mode on for this message (the settings or #rychle)."""
    return apply_tags(clean(settings), tags)["lean"]


WORKSPACES = ("quick", "model", "assembly", "sheet", "drawing")


def tool_group(workspace) -> str:
    """The workspace on screen -> its tool group (agent_tools.TOOL_GROUPS) for ⚡ Lean mode; another (the start
    screen): only the general tools."""
    return workspace if workspace in WORKSPACES else "general"


def save_internet(data_dir, on: bool) -> bool:
    """🌐 Search the internet for parts (the project's setting) -> <data>/ai/settings.json {"internet"} (what the chat's
    start reads) -> whether it changed (none there: on)."""
    path = Path(data_dir) / "ai" / "settings.json"
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        old = old if isinstance(old, dict) else {}
    except (OSError, ValueError):
        old = {}
    if (old.get("internet", True) is not False) == bool(on):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**old, "internet": bool(on)}), encoding="utf-8")
    return True
