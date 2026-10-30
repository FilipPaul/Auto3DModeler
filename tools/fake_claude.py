"""A stand-in for Claude Code in the chat's browser tests (no model, no sign-in): the server runs it when AUTO3D_CLAUDE
points at it. It speaks stream-json like `claude -p --input-format stream-json --output-format stream-json`: an init
with its session id, then for each message a tool line and an answer that tells what it got —

  "Echo #<n in this session>: <the message's first words> | resumed: <session id or no> | summary: <yes / no>"

Its sessions are files under $CLAUDE_CONFIG_DIR/projects/fake/<id>.jsonl (where the server looks for a session to
resume); `--resume <id>` of a session that is not there fails as Claude Code does ("No conversation found …", exit 1).
A message with "SLOW" in it is answered slowly: a piece of text every 0.5 s for a minute first (to press Stop in).
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path


def out(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    args = sys.argv[1:]
    if args[:2] == ["auth", "status"]:  # (the ✨ AI panel asks whether it is signed in)
        out({"loggedIn": True, "authMethod": "fake", "email": "fake@example.com"})
        return
    resume = args[args.index("--resume") + 1] if "--resume" in args else None
    folder = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude-fake") / "projects" / "fake"
    folder.mkdir(parents=True, exist_ok=True)
    if resume and not (folder / f"{resume}.jsonl").exists():
        sys.stderr.write(f"No conversation found with session ID: {resume}\n")
        sys.exit(1)
    sid = resume or str(uuid.uuid4())
    log = folder / f"{sid}.jsonl"
    n = len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0
    out({"type": "system", "subtype": "init", "session_id": sid, "model": "fake-claude",
         "mcp_servers": [{"name": "auto3d", "status": "connected"}]})
    for raw in iter(sys.stdin.buffer.readline, b""):
        try:
            msg = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        text = [b["text"] for b in msg["message"]["content"] if b.get("type") == "text"][-1]
        n += 1
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"text": text}) + "\n")
        summary = "yes" if text.startswith("[This continues an earlier conversation") else "no"
        said = text.split("]\n\n", 1)[1] if summary == "yes" else text
        out({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "mcp__auto3d__get_model", "input": {}}]}})
        out({"type": "user", "message": {"content": [{"type": "tool_result", "content": "a model"}]}})
        if "SLOW" in said:
            out({"type": "stream_event", "event": {"type": "message_start"}})
            for i in range(120):
                out({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": f"{i} "}}})
                time.sleep(0.5)
        out({"type": "assistant", "message": {"content": [{"type": "text", "text":
             f"Echo #{n}: {said[:60]} | resumed: {resume or 'no'} | summary: {summary}"}]}})
        out({"type": "result", "is_error": False, "result": "", "total_cost_usd": 0, "duration_ms": 1})


if __name__ == "__main__":
    main()
