"""Environment-derived configuration (store root, machine id, sync remote).

Kept free of any FastMCP dependency so the CLI hot path (inject/capture/sync)
works without the optional ``mcp`` extra; ``server.py`` imports these too.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path


def resolve_home() -> Path:
    """Resolve the store root from ``ANAMNESIS_HOME`` (default ``~/.anamnesis``)."""
    raw = os.environ.get("ANAMNESIS_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".anamnesis"


def resolve_machine_id() -> str:
    """Resolve this machine's id from ``ANAMNESIS_MACHINE_ID`` (default hostname)."""
    return os.environ.get("ANAMNESIS_MACHINE_ID") or socket.gethostname() or "unknown"


def resolve_remote() -> str | None:
    """Resolve the sync remote from ``ANAMNESIS_GIT_REMOTE`` (None if unset)."""
    return os.environ.get("ANAMNESIS_GIT_REMOTE") or None
