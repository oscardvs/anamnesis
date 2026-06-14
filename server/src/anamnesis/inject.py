"""SessionStart memory injection: select and render notes for a project.

Pure reads over :class:`MemoryStore` (no FastMCP, no network). ``resolve_project_key``
derives a v0 project identity from the working directory; a stable cross-machine
identity (git remote / repo marker) is a planned follow-up, deliberately isolated
in this one function.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _normalize_remote(url: str) -> str:
    """Normalize a git remote URL to a stable lowercased key (no scheme/user/.git)."""
    u = url.strip()
    u = re.sub(r"^\w+://", "", u)  # strip scheme: https:// ssh:// git://
    u = re.sub(r"^[^@/]+@", "", u)  # strip user@
    if ":" in u and "/" not in u.split(":", 1)[0]:
        u = u.replace(":", "/", 1)  # scp form host:path -> host/path
    u = re.sub(r"\.git$", "", u)
    return u.rstrip("/").lower()


def resolve_project_key(cwd: str | Path) -> str:
    """Best-effort stable project key from a working directory (v0 heuristic).

    Order: normalized ``origin`` remote, else repo-root dirname, else cwd basename.
    """
    cwd = Path(cwd)
    try:
        remote = subprocess.run(
            ["git", "-C", str(cwd), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        if remote.returncode == 0 and remote.stdout.strip():
            return _normalize_remote(remote.stdout.strip())
        root = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if root.returncode == 0 and root.stdout.strip():
            return Path(root.stdout.strip()).name.lower()
    except OSError:
        pass
    return (cwd.name or "global").lower()
