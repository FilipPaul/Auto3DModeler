"""The workflow guides for the AI: the skills in agent_plugin/skills/*/SKILL.md (Claude Code loads them as the
"auto3d" plugin) — the same texts are served by the MCP server as the get_guide tool and as MCP prompts, for
clients without skills. One source of truth. Standard library only (the MCP server imports it).
"""
from __future__ import annotations

from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "agent_plugin"
SKILLS_DIR = PLUGIN_DIR / "skills"


def _parse(text: str):
    """SKILL.md -> (frontmatter dict, body)."""
    meta, body = {}, text
    if text.startswith("---"):
        head, _, body = text[3:].partition("\n---")
        for line in head.strip().splitlines():
            k, _, v = line.partition(":")
            if k.strip():
                meta[k.strip()] = v.strip()
        body = body.lstrip("\n")
    return meta, body


def guides() -> dict:
    """{name: {"description", "text"}} for every skill."""
    out = {}
    for f in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        meta, body = _parse(f.read_text(encoding="utf-8"))
        name = meta.get("name") or f.parent.name
        out[name] = {"description": meta.get("description", ""), "text": body}
    return out


def guide(name: str) -> str:
    g = guides()
    if name in g:
        return g[name]["text"]
    raise KeyError(f"No guide “{name}”. Guides: {', '.join(g)}.")
