"""The ``anamnesis`` command-line entry point.

Subcommands the Claude Code hooks invoke (architecture section 5.2): ``serve``
(the MCP server), ``sync``, ``status``, ``inject`` (SessionStart), ``capture``
(SessionEnd / PreCompact). Kept free of FastMCP except inside ``serve`` so the
hook hot path works without the optional ``mcp`` extra.
"""

from __future__ import annotations

import argparse
import json
import sys

from anamnesis.config import resolve_home
from anamnesis.inject import render_inject, resolve_project_key, select_inject
from anamnesis.store import MemoryStore


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="anamnesis", description="Cross-machine memory for Claude Code."
    )
    sub = p.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")
    sub.add_parser("sync", help="run one git sync cycle and reindex")
    sub.add_parser("status", help="print store and sync status")
    pi = sub.add_parser("inject", help="print top notes for the project as SessionStart context")
    pi.add_argument("--project", default=None)
    pi.add_argument("--k", type=int, default=8)
    pc = sub.add_parser("capture", help="write an episodic note from a transcript")
    pc.add_argument("--transcript", default=None)
    pc.add_argument("--project", default=None)
    pc.add_argument("--source", default="session-end")
    pc.add_argument("--no-sync", action="store_true")
    return p


def resolve_command(argv: list[str]) -> str:
    """The subcommand to run, defaulting to ``serve`` when none is given."""
    return build_parser().parse_args(argv).command or "serve"


def read_hook_payload() -> dict[str, object]:
    """Read the hook JSON payload from stdin (empty dict if none, piped, or invalid)."""
    stdin = sys.stdin
    if stdin is None or stdin.isatty():
        return {}
    try:
        raw = stdin.read()
    except (OSError, ValueError):
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def cmd_inject(args: argparse.Namespace, payload: dict[str, object]) -> int:
    """SessionStart: print top notes for the session's project to stdout."""
    store = MemoryStore(resolve_home())
    try:
        project = args.project or resolve_project_key(str(payload.get("cwd") or "."))
        text = render_inject(select_inject(store, project=project, k=args.k))
        if text:
            sys.stdout.write(text)
    finally:
        store.close()
    return 0
