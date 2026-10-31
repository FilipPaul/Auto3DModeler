"""Files attached to an AI chat message (📎 Attachment) other than photos: each is saved under the chat's attachments
folder, and the message to Claude says where. A text file (notes, a CSV, a log, source code) also goes into the
message as a fenced block with its name — whole up to TEXT_FILE_CAP, else its first HEAD_LINES lines; the texts of one
message together stay under TEXT_TOTAL_CAP (about 40k tokens). CAD files and drawings (STEP, STL, DXF, PDF, Gerber …)
are only named, so the AI opens them with its tools (open_file, trace_picture, the drawing tools).

Text is read as UTF-8 when it is UTF-8, else in the Windows code page it most likely is (Czech cp1250 or Western
cp1252, told apart by letters rare in each — the same idea as the STEP names in modeler/kernel.py), never mojibake.
"""
import re
import time
import uuid
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml", ".log", ".ini", ".cfg", ".conf", ".toml",
            ".py", ".js", ".mjs", ".ts", ".html", ".css", ".c", ".h", ".cpp", ".hpp", ".cs", ".java", ".sql", ".sh",
            ".bat", ".ps1", ".vb", ".bas", ".gcode", ".nc"}
FILE_EXT = {".step", ".stp", ".igs", ".iges", ".stl", ".obj", ".3mf", ".dxf", ".dwg", ".pdf", ".zip", ".a3d", ".svg"}
MAX_FILES = 10                       # attachments per message (photos included)
MAX_FILE_BYTES = 50 * 1024 * 1024    # one file's upload
TEXT_FILE_CAP = 60 * 1024            # a text file whole in the message up to this ...
TEXT_TOTAL_CAP = 150 * 1024          # ... and the texts of one message together (≈ 40k tokens)
HEAD_LINES, HEAD_BYTES = 200, 16 * 1024  # a larger one: its head

# Letters rare in the languages of a code page: what its bytes give when the text is in the other one (a Czech
# ě ř ů ň read as Western are ì ø ù ò; a French à û read as Central are ŕ ű). Bytes a page lacks count too.
_RARE = {"cp1250": set("ŕĺăţőűŔĹĂŢŐŰ") | {chr(0xFFFD)}, "cp1252": set("ìòøùïðþÌÒØÙÏÐÞ") | {chr(0xFFFD)}}


def kind(name: str):
    """'text', 'file' (saved and named) or None (a type not attached) for a file name."""
    ext = Path(name or "").suffix.lower()
    return "text" if ext in TEXT_EXT else "file" if ext in FILE_EXT else None


def decode_text(raw: bytes) -> tuple[str, str]:
    """A text file's bytes -> (text, its encoding): UTF-8 (a BOM dropped; UTF-16 by its BOM), else cp1250 / cp1252."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace"), "utf-8"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace"), "utf-16"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    high = b" ".join(re.findall(rb"[\x80-\xff]+", raw))
    rare = {cp: sum(c in _RARE[cp] for c in high.decode(cp, errors="replace")) for cp in _RARE}
    cp = "cp1252" if rare["cp1252"] < rare["cp1250"] else "cp1250"
    return raw.decode(cp, errors="replace"), cp


def size_label(n: int) -> str:
    """1 234 567 -> '1.2 MB', 2048 -> '2 kB', 300 -> '300 B'."""
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{max(1, round(n / 1024))} kB" if n >= 1024 else f"{n} B"


def _fence(text: str) -> str:
    """A code fence longer than any run of backticks in the text."""
    return "`" * max(3, 1 + max((len(m) for m in re.findall(r"`+", text)), default=0))


def head(text: str, lines: int = HEAD_LINES, cap: int = HEAD_BYTES) -> tuple[str, int]:
    """The first `lines` lines of a text, cut to `cap` bytes (whole lines) -> (head, lines in it)."""
    out, size = [], 0
    for line in text.splitlines()[:lines]:
        b = len(line.encode("utf-8")) + 1
        if size + b > cap:
            if not out:  # (one very long first line: its start)
                out.append(line.encode("utf-8")[:cap].decode("utf-8", errors="ignore"))
            break
        out.append(line)
        size += b
    return "\n".join(out), len(out)


def block(name: str, path: str, raw: bytes, room: int) -> tuple[str, int]:
    """The message's part for one text file -> (its text, bytes of the file's text used). `room`: what is left of
    TEXT_TOTAL_CAP for this message; a file larger than that or TEXT_FILE_CAP goes in as its head."""
    text, enc = decode_text(raw)
    used = len(text.encode("utf-8"))
    lang = Path(name).suffix.lower().lstrip(".")
    enc_note = "" if enc == "utf-8" else f", {enc}"
    if used <= min(TEXT_FILE_CAP, room):
        body, label = text, f"[Attached file: {path}, {size_label(len(raw))}{enc_note}]"
    else:
        body, n = head(text, cap=min(HEAD_BYTES, max(room, 0)))
        used = len(body.encode("utf-8"))
        label = (f"[Attached file: {path}, {size_label(len(raw))}{enc_note}, first {n} lines included]" if n
                 else f"[Attached file: {path}, {size_label(len(raw))}{enc_note} — too long to include, read it from the file]")
        if not n:
            return label, 0
    f = _fence(body)
    return f"{label}\n{name}:\n{f}{lang}\n{body}\n{f}", used


def save(folder: Path, name: str, raw: bytes) -> Path:
    """The file kept under `folder` with a unique, readable name -> its path."""
    p = Path(name or "file")
    stem = re.sub(r"[^\w.-]+", "_", p.stem)[:40] or "file"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}-{stem}{p.suffix.lower()}"
    out.write_bytes(raw)
    return out


def attach(folder: Path, files: list[tuple[str, bytes]]) -> list[dict]:
    """[(name, bytes)] -> [{name, size, kind, path, text}]: each saved; `text` is what the message to Claude says of it.
    Raises ValueError (an in-app message) for an unknown type or a file too big — before any is saved."""
    out, room = [], TEXT_TOTAL_CAP
    for name, raw in files[:MAX_FILES]:
        k = kind(name)
        if k is None:
            raise ValueError(f"{name}: this type of file cannot be attached yet.")
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError(f"{name} is larger than {MAX_FILE_BYTES // 1048576} MB.")
    for name, raw in files[:MAX_FILES]:
        path = str(save(folder, name, raw))
        if kind(name) == "text":
            text, used = block(name, path, raw, room)
            room -= used
        else:
            text = f"[Attached file: {path}]"
        out.append({"name": name, "size": len(raw), "kind": kind(name), "path": path, "text": text})
    return out
