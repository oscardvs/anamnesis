"""Environment-derived configuration (store root, machine id, sync remote).

Kept free of any FastMCP dependency so the CLI hot path (inject/capture/sync)
works without the optional ``mcp`` extra; ``server.py`` imports these too.
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any


def resolve_home() -> Path:
    """Resolve the store root from ``ANAMNESIS_HOME`` (default ``~/.anamnesis``)."""
    raw = os.environ.get("ANAMNESIS_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".anamnesis"


def resolve_claude_home() -> Path:
    """Claude Code's config dir: ``CLAUDE_CONFIG_DIR`` (as ``init`` uses), else ``~/.claude``.

    Its ``projects/<slug>/memory`` trees hold Claude's native per-project memory,
    which the importer mirrors into the Anamnesis store.
    """
    raw = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(raw).expanduser() if raw else Path.home() / ".claude"


def _store_config() -> dict[str, Any]:
    """Best-effort read of the per-store ``config.json`` (machine-local, never synced).

    Written by ``anamnesis init``; lives at ``<home>/config.json``, outside the
    synced ``memory/`` repo (the remote URL differs per machine). Missing or
    malformed files yield ``{}`` so resolution never fails on a bad config.
    """
    try:
        data = json.loads((resolve_home() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _config_str(key: str) -> str | None:
    """A non-empty string value from the store config, else None."""
    value = _store_config().get(key)
    return value if isinstance(value, str) and value else None


def resolve_machine_id() -> str:
    """This machine's id: ``ANAMNESIS_MACHINE_ID``, else store config, else hostname."""
    return (
        os.environ.get("ANAMNESIS_MACHINE_ID")
        or _config_str("machine_id")
        or socket.gethostname()
        or "unknown"
    )


def resolve_remote() -> str | None:
    """The sync remote: ``ANAMNESIS_GIT_REMOTE``, else store config, else None.

    The store-config fallback lets the MCP server (launched via ``.mcp.json``
    without inline env) and the dashboard find the remote, so an in-session
    ``memory_sync`` pushes rather than only committing locally.
    """
    return os.environ.get("ANAMNESIS_GIT_REMOTE") or _config_str("remote")
