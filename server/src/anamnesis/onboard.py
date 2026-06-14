"""``anamnesis init``: configure Claude Code (MCP + hooks), the store, and first sync.

The logic is generic and tested with synthetic fixtures; the side effects (stdin
prompts, the ``claude`` subprocess, PATH lookup) are injected so the orchestrator
is fully testable. It only touches the real ``~/.claude`` at runtime on a user's
machine. See docs/superpowers/specs/2026-06-14-init-onboarding-design.md.
"""

from __future__ import annotations

import shlex
import shutil
from collections.abc import Callable
from pathlib import Path

Which = Callable[[str], str | None]


def _default_which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _server_dir() -> Path:
    """The editable checkout's ``server/`` dir (this package lives at server/src/anamnesis)."""
    return Path(__file__).resolve().parents[2]


def detect_command(
    *,
    override_command: str | None = None,
    override_uv_project: str | None = None,
    which: Which = _default_which,
) -> list[str]:
    """The base argv used to invoke ``anamnesis`` from hooks and the MCP entry.

    Resolution order: explicit ``--command`` override; ``--uv-project`` override;
    an installed ``anamnesis`` on PATH; else ``uv run --project <server>`` fallback.
    """
    if override_command:
        return shlex.split(override_command)
    if override_uv_project:
        uv = which("uv") or "uv"
        project = str(Path(override_uv_project).expanduser().resolve())
        return [uv, "run", "--project", project, "anamnesis"]
    found = which("anamnesis")
    if found:
        return [str(Path(found).resolve())]
    uv = which("uv") or "uv"
    return [uv, "run", "--project", str(_server_dir()), "anamnesis"]
