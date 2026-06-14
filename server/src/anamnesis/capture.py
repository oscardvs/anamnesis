"""SessionEnd / PreCompact capture: turn a Claude Code transcript into an episodic
note. The v0 summary is deterministic and lives behind a swappable ``Summarizer``
so the Phase 2 reflection model (architecture section 6) can slot in via config.

This is generic transcript-to-note logic with no hardcoded ``~/.claude`` paths; it
is tested with synthetic fixtures and touches real data only when a hook passes a
real transcript path at runtime.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from anamnesis.store import Memory, MemoryStore

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


_MAX_LEN = 600


def _clip(text: str, limit: int = _MAX_LEN) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " ..."


class Summarizer(Protocol):
    """Turns a parsed session into an episodic note (title, body)."""

    def summarize(self, session: ParsedSession) -> tuple[str, str]: ...


class HeuristicSummarizer:
    """Deterministic v0 summary: the ask, the branch, files touched, the outcome."""

    def summarize(self, session: ParsedSession) -> tuple[str, str]:
        first = session.first_prompt
        title = first.splitlines()[0][:80] if first else "Session summary"
        parts = [f"**Ask:** {_clip(first) or '(no user prompt captured)'}", ""]
        if session.git_branch:
            parts.append(f"**Branch:** {session.git_branch}")
        if session.files_touched:
            parts.append(f"**Files touched ({len(session.files_touched)}):**")
            parts.extend(f"- {p}" for p in session.files_touched)
        parts.append("")
        outcome = _clip(session.last_outcome) or "(no assistant output captured)"
        parts.append(f"**Outcome:** {outcome}")
        return title, "\n".join(parts)


def _make_heuristic() -> Summarizer:
    return HeuristicSummarizer()


_SUMMARIZERS: dict[str, Callable[[], Summarizer]] = {"heuristic": _make_heuristic}


def resolve_summarizer() -> Summarizer:
    """Pick the summarizer from ``ANAMNESIS_REFLECTION_PROVIDER`` (default heuristic).

    v0 only ships the deterministic summarizer; an LLM-backed reflection model
    (architecture section 6) registers here later with no call-site changes.
    """
    provider = os.environ.get("ANAMNESIS_REFLECTION_PROVIDER", "heuristic").lower()
    return _SUMMARIZERS.get(provider, _make_heuristic)()


def write_episodic(
    store: MemoryStore,
    session: ParsedSession,
    *,
    summarizer: Summarizer,
    project: str,
    source: str,
    machine_id: str,
) -> Memory:
    """Build and persist the episodic note. No sync; the caller orchestrates that.

    ``source`` (``session-end`` or ``precompact``) is recorded as a tag for now; a
    first-class ``prov_source`` column is a backlog follow-up (architecture section 8).
    """
    title, body = summarizer.summarize(session)
    return store.write(
        type="episodic",
        title=title,
        body=body,
        project=project,
        machine_id=machine_id,
        tags=["session", source],
    )
