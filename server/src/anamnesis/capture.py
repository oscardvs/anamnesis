"""SessionEnd / PreCompact capture: turn a Claude Code transcript into an episodic
note. The v0 summary is deterministic and lives behind a swappable ``Summarizer``
so the Phase 2 reflection model (architecture section 6) can slot in via config.

This is generic transcript-to-note logic with no hardcoded ``~/.claude`` paths; it
is tested with synthetic fixtures and touches real data only when a hook passes a
real transcript path at runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


@dataclass
class ParsedSession:
    """Deterministic facts extracted from a transcript (all best-effort)."""

    first_prompt: str = ""
    last_outcome: str = ""
    files_touched: list[str] = field(default_factory=list)
    git_branch: str = ""
    cwd: str = ""
    session_id: str = ""


def _text_of(content: object) -> str:
    """Join the text of a message ``content`` (a string, or a list of blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                t = b.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)
    return ""


def parse_transcript(path: str | Path) -> ParsedSession:
    """Tolerantly extract a deterministic session summary from a transcript JSONL.

    An unreadable file or malformed lines degrade to an empty/partial result rather
    than raising, so capture never breaks session teardown.
    """
    session = ParsedSession()
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return session

    last_text = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue

        if ev.get("cwd") and not session.cwd:
            session.cwd = str(ev["cwd"])
        if ev.get("gitBranch") and not session.git_branch:
            session.git_branch = str(ev["gitBranch"])
        if ev.get("sessionId") and not session.session_id:
            session.session_id = str(ev["sessionId"])

        etype = ev.get("type")
        msg = ev.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None

        if etype == "user" and not ev.get("isMeta"):
            text = _text_of(content).strip()
            if text and not session.first_prompt:
                session.first_prompt = text
        elif etype == "assistant":
            text = _text_of(content).strip()
            if text:
                last_text = text
            if isinstance(content, list):
                for b in content:
                    if (
                        isinstance(b, dict)
                        and b.get("type") == "tool_use"
                        and b.get("name") in _EDIT_TOOLS
                    ):
                        inp = b.get("input")
                        fp = inp.get("file_path") if isinstance(inp, dict) else None
                        if isinstance(fp, str) and fp not in session.files_touched:
                            session.files_touched.append(fp)

    session.last_outcome = last_text
    return session
