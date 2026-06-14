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


def build_env(*, machine_id: str, remote: str | None, home: Path | None) -> dict[str, str]:
    """The ``ANAMNESIS_*`` values to embed (machine id always; remote/home when set).

    ``home`` is passed only when it differs from the ``~/.anamnesis`` default; the
    caller decides that and passes ``None`` to omit it.
    """
    env = {"ANAMNESIS_MACHINE_ID": machine_id}
    if remote:
        env["ANAMNESIS_GIT_REMOTE"] = remote
    if home is not None:
        env["ANAMNESIS_HOME"] = str(home)
    return env


HookEntry = dict[str, object]
HooksMap = dict[str, list[HookEntry]]


def _command_string(env: dict[str, str], base: list[str], *args: str) -> str:
    """A shell-form hook command: ``KEY=val ... <base> <args>`` with values quoted."""
    prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    cmd = " ".join(shlex.quote(p) for p in [*base, *args])
    return f"{prefix} {cmd}" if prefix else cmd


def build_hooks(base: list[str], env: dict[str, str]) -> HooksMap:
    """The four lifecycle hooks (matching examples/hooks.settings.json) with inline env."""
    return {
        "SessionStart": [
            {
                "matcher": "startup|resume|clear",
                "hooks": [
                    {
                        "type": "command",
                        "command": _command_string(env, base, "inject"),
                        "timeout": 15,
                    }
                ],
            },
            {
                "matcher": "startup|resume",
                "hooks": [
                    {
                        "type": "command",
                        "command": _command_string(env, base, "sync"),
                        "async": True,
                    }
                ],
            },
        ],
        "SessionEnd": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": _command_string(env, base, "capture"),
                        "timeout": 120,
                    }
                ]
            }
        ],
        "PreCompact": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": _command_string(
                            env, base, "capture", "--source", "precompact", "--no-sync"
                        ),
                        "timeout": 60,
                    }
                ]
            }
        ],
    }
