"""``anamnesis init``: configure Claude Code (MCP + hooks), the store, and first sync.

The logic is generic and tested with synthetic fixtures; the side effects (stdin
prompts, the ``claude`` subprocess, PATH lookup) are injected so the orchestrator
is fully testable. It only touches the real ``~/.claude`` at runtime on a user's
machine. See docs/superpowers/specs/2026-06-14-init-onboarding-design.md.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import socket
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anamnesis.store import MemoryStore
from anamnesis.sync import GitSyncBackend, SyncError

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


def build_mcp_add_argv(base: list[str], env: dict[str, str], name: str = "anamnesis") -> list[str]:
    """``claude mcp add`` argv registering the stdio server at user scope with env.

    The name comes BEFORE the ``-e`` flags: claude's ``-e/--env`` is variadic, so
    placing the name after it makes the parser consume the name as an env value.
    The command follows a ``--`` separator. See ``claude mcp add --help``.
    """
    argv = ["claude", "mcp", "add", "--scope", "user", "--transport", "stdio", name]
    for k, v in env.items():
        argv += ["-e", f"{k}={v}"]
    argv += ["--", *base, "serve"]
    return argv


def build_mcp_remove_argv(name: str = "anamnesis") -> list[str]:
    """``claude mcp remove`` argv (best-effort, for idempotent re-registration)."""
    return ["claude", "mcp", "remove", "--scope", "user", name]


# Markers that identify a hook command this tool installs, independent of the
# resolved command form: the inline ANAMNESIS_ env prefix (always present, since
# build_env always sets ANAMNESIS_MACHINE_ID) plus the subcommand invocations
# (which also match groups written by older versions without an env prefix).
_HOOK_MARKERS = ("ANAMNESIS_", "anamnesis inject", "anamnesis sync", "anamnesis capture")


def _is_anamnesis_group(group: Any) -> bool:
    """True if a matcher-group holds a command this tool installs (by command marker)."""
    if not isinstance(group, dict):
        return False
    hooks = group.get("hooks")
    if not isinstance(hooks, list):
        return False
    for h in hooks:
        cmd = h.get("command") if isinstance(h, dict) else None
        if isinstance(cmd, str) and any(m in cmd for m in _HOOK_MARKERS):
            return True
    return False


def merge_hooks(settings: dict[str, Any], new_hooks: HooksMap) -> dict[str, Any]:
    """Merge our hooks into existing settings idempotently.

    Drops any prior anamnesis matcher-groups (identified by command marker), keeps
    every other top-level key and any non-anamnesis hooks, then inserts ours.
    """
    result: dict[str, Any] = dict(settings)
    existing = result.get("hooks")
    merged: dict[str, list[Any]] = {}
    if isinstance(existing, dict):
        for event, groups in existing.items():
            if isinstance(groups, list):
                kept = [g for g in groups if not _is_anamnesis_group(g)]
                if kept:
                    merged[event] = kept
            else:
                merged[event] = groups
    for event, groups in new_hooks.items():
        prev = merged.get(event, [])
        if not isinstance(prev, list):
            prev = []
        merged[event] = [*prev, *groups]
    result["hooks"] = merged
    return result


def claude_dir() -> Path:
    """Claude Code's config dir (``CLAUDE_CONFIG_DIR`` or ``~/.claude``)."""
    raw = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(raw).expanduser() if raw else Path.home() / ".claude"


def read_settings(path: Path) -> dict[str, Any]:
    """Parse a settings JSON object, or ``{}`` if missing/empty. Raises on a non-object."""
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def write_settings(path: Path, data: dict[str, Any]) -> None:
    """Write settings atomically, backing up an existing file to ``<name>.bak`` once."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    text = json.dumps(data, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-anamnesis-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_store_config(home: Path, *, machine_id: str, remote: str | None) -> None:
    """Persist machine-local config so any launch of the server/CLI finds the remote.

    Lives at ``<home>/config.json``, outside the synced ``memory/`` repo (the
    remote URL differs per machine, so this must never sync). ``config.resolve_*``
    read it as a fallback; env vars still take precedence. This is what lets the
    MCP server (launched without inline env) push on ``memory_sync``.
    """
    home.mkdir(parents=True, exist_ok=True)
    cfg: dict[str, str] = {"machine_id": machine_id}
    if remote:
        cfg["remote"] = remote
    (home / "config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


Prompt = Callable[[str, str], str]
Runner = Callable[[list[str]], tuple[int, str]]

_DEFAULT_HOME = Path.home() / ".anamnesis"


def default_prompt(label: str, default: str) -> str:
    """Non-interactive prompt: always take the default (used with ``--yes``)."""
    return default


def tty_prompt(label: str, default: str) -> str:
    """Interactive prompt: read a line, falling back to the default on blank input or EOF."""
    try:
        raw = input(f"{label} [{default}]: ").strip()
    except EOFError:
        return default
    return raw or default


def subprocess_runner(argv: list[str]) -> tuple[int, str]:
    """Run a command, returning (returncode, combined stdout+stderr)."""
    proc = subprocess.run(argv, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


@dataclass
class InitOptions:
    """Raw inputs to ``run_init`` (from CLI flags); ``run_init`` resolves the rest."""

    home: Path | None = None
    machine_id: str | None = None
    remote: str | None = None
    local_only: bool = False
    override_command: str | None = None
    override_uv_project: str | None = None
    name: str = "anamnesis"
    no_mcp: bool = False
    no_hooks: bool = False
    no_sync: bool = False
    yes: bool = False
    print_only: bool = False


def _resolve_remote(opts: InitOptions, prompt: Prompt) -> str | None:
    if opts.local_only:
        return None
    if opts.remote:
        return opts.remote
    if opts.yes:
        return None
    return prompt("sync remote (blank = local-only)", "") or None


def run_init(
    opts: InitOptions,
    *,
    prompt: Prompt | None = None,
    runner: Runner = subprocess_runner,
    which: Which = _default_which,
) -> int:
    """Configure Claude Code (MCP + hooks), set up the store, and run a first sync."""
    if prompt is None:
        prompt = default_prompt if (opts.yes or opts.print_only) else tty_prompt
    home = opts.home or (
        _DEFAULT_HOME if opts.yes else Path(prompt("store home", str(_DEFAULT_HOME))).expanduser()
    )
    machine_id = opts.machine_id or (
        socket.gethostname() if opts.yes else prompt("machine id", socket.gethostname())
    )
    remote = _resolve_remote(opts, prompt)
    base = detect_command(
        override_command=opts.override_command,
        override_uv_project=opts.override_uv_project,
        which=which,
    )
    if not opts.yes and not opts.override_command and not opts.override_uv_project:
        shown = " ".join(base)
        entered = prompt("command form", shown)
        if entered and entered != shown:
            base = shlex.split(entered)
    env = build_env(
        machine_id=machine_id,
        remote=remote,
        home=None if home == _DEFAULT_HOME else home,
    )

    if opts.print_only:
        print("init plan (dry-run; nothing written):")
        print(f"  store home : {home}")
        print(f"  machine id : {machine_id}")
        print(f"  remote     : {remote or '(local-only)'}")
        print(f"  command    : {' '.join(base)}")
        print(f"  config     : {home / 'config.json'}")
        if not opts.no_mcp:
            print(f"  mcp add    : {' '.join(build_mcp_add_argv(base, env, opts.name))}")
        if not opts.no_hooks:
            print(
                f"  hooks      : {', '.join(build_hooks(base, env))}"
                f" -> {claude_dir() / 'settings.json'}"
            )
        return 0

    # Pre-flight: fail fast on an unparseable settings file BEFORE any side effect.
    settings_path = claude_dir() / "settings.json"
    existing_settings: dict[str, Any] = {}
    if not opts.no_hooks:
        try:
            existing_settings = read_settings(settings_path)
        except ValueError as exc:
            print(
                f"init: refusing to run; {settings_path} is not valid JSON"
                f" ({exc}); fix it and re-run"
            )
            return 1

    if not opts.no_mcp:
        if which("claude"):
            runner(build_mcp_remove_argv(opts.name))
            rc, out = runner(build_mcp_add_argv(base, env, opts.name))
            print(
                f"mcp: registered {opts.name} (user scope)"
                if rc == 0
                else f"mcp: add failed: {out.strip()}"
            )
        else:
            print("mcp: `claude` not found on PATH; run this yourself:")
            print(f"  {' '.join(build_mcp_add_argv(base, env, opts.name))}")

    if not opts.no_hooks:
        merged = merge_hooks(existing_settings, build_hooks(base, env))
        write_settings(settings_path, merged)
        print(f"hooks: installed SessionStart/SessionEnd/PreCompact -> {settings_path}")

    # Persist machine-local config (remote + machine id) so any later launch of
    # the server/CLI finds the remote, even when started without inline env.
    write_store_config(home, machine_id=machine_id, remote=remote)
    print(f"config: wrote {home / 'config.json'}")

    if not opts.no_sync:
        store = MemoryStore(home)
        try:
            backend = GitSyncBackend(store.memory_dir, remote=remote, machine_id=machine_id)
            try:
                result = backend.sync()
                store.reindex()
                print(f"sync: pushed={result.pushed} pulled={result.pulled} ({result.detail})")
            except SyncError as exc:
                print(f"sync: skipped ({exc}); fix the remote and run `anamnesis sync`")
        finally:
            store.close()

    print(
        "init: done. Start a new Claude Code session for the MCP server and hooks to take effect."
    )
    return 0
