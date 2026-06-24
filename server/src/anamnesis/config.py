"""Environment-derived configuration (store root, machine id, sync remote).

Kept free of any FastMCP dependency so the CLI hot path (inject/capture/sync)
works without the optional ``mcp`` extra; ``server.py`` imports these too.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ReflectionSettings:
    """Merged reflection/LLM config: env var > config.json reflection.* > default."""

    provider: str
    model: str
    base_url: str
    api_key: str
    timeout: float
    max_tokens: int


def _reflection_block() -> dict[str, Any]:
    block = _store_config().get("reflection")
    return block if isinstance(block, dict) else {}


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) and value else ""


def _float_setting(env_name: str, file_value: Any, default: float) -> float:
    raw: Any = os.environ.get(env_name)
    if raw is None:
        raw = file_value
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def resolve_reflection_provider() -> str:
    """The reflection provider: env > config.json > 'heuristic' (lowercased)."""
    raw = (
        os.environ.get("ANAMNESIS_REFLECTION_PROVIDER")
        or _as_str(_reflection_block().get("provider"))
        or "heuristic"
    )
    return raw.lower()


def resolve_reflection_settings() -> ReflectionSettings:
    """Full reflection config with env > file > default precedence per field."""
    block = _reflection_block()
    api_key = (
        os.environ.get("ANAMNESIS_REFLECTION_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or _as_str(block.get("api_key"))
    )
    return ReflectionSettings(
        provider=resolve_reflection_provider(),
        model=os.environ.get("ANAMNESIS_REFLECTION_MODEL") or _as_str(block.get("model")),
        base_url=os.environ.get("ANAMNESIS_REFLECTION_BASE_URL") or _as_str(block.get("base_url")),
        api_key=api_key,
        timeout=_float_setting("ANAMNESIS_REFLECTION_TIMEOUT", block.get("timeout"), 30.0),
        max_tokens=int(
            _float_setting("ANAMNESIS_REFLECTION_MAX_TOKENS", block.get("max_tokens"), 120000.0)
        ),
    )
