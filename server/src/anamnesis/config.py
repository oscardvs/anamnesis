"""Environment-derived configuration (store root, machine id, sync remote).

Kept free of any FastMCP dependency so the CLI hot path (inject/capture/sync)
works without the optional ``mcp`` extra; ``server.py`` imports these too.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
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


def _read_config(home: Path) -> dict[str, Any]:
    try:
        data = json.loads((home / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _store_config() -> dict[str, Any]:
    """Best-effort read of the per-store ``config.json`` (machine-local, never synced).

    Written by ``anamnesis init``; lives at ``<home>/config.json``, outside the
    synced ``memory/`` repo (the remote URL differs per machine). Missing or
    malformed files yield ``{}`` so resolution never fails on a bad config.
    """
    return _read_config(resolve_home())


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


UNSET = object()  # sentinel: passed as an update value to remove a key


def save_store_config(home: Path, config: dict[str, Any]) -> None:
    """Atomically write config.json (temp + replace) with owner-only (0600) perms.

    Backs up an existing file to ``config.json.bak`` once. The key may live here,
    so the file must never be group/world readable.
    """
    home.mkdir(parents=True, exist_ok=True)
    path = home / "config.json"
    bak = path.with_name("config.json.bak")
    if path.exists() and not bak.exists():
        shutil.copy2(path, bak)
    text = json.dumps(config, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(home), prefix=".tmp-anamnesis-")
    try:
        os.chmod(tmp, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def update_store_config(home: Path, updates: dict[str, Any]) -> None:
    """Apply dotted-key updates to config.json, then save atomically.

    ``"reflection.model": "x"`` sets a nested value; ``"reflection.model": UNSET``
    removes it (pruning an emptied ``reflection`` block).
    """
    config = _read_config(home)
    for dotted, value in updates.items():
        parts = dotted.split(".")
        node = config
        for key in parts[:-1]:
            child = node.get(key)
            if not isinstance(child, dict):
                child = {}
                node[key] = child
            node = child
        leaf = parts[-1]
        if value is UNSET:
            node.pop(leaf, None)
        else:
            node[leaf] = value
    if isinstance(config.get("reflection"), dict) and not config["reflection"]:
        config.pop("reflection")
    save_store_config(home, config)


_PROVIDERS = ("heuristic", "deepseek", "openai", "local")
KNOWN_KEYS = (
    "machine_id",
    "remote",
    "reflection.provider",
    "reflection.model",
    "reflection.base_url",
    "reflection.api_key",
    "reflection.timeout",
    "reflection.max_tokens",
)


def validate_setting(key: str, value: str) -> Any:
    """Validate and coerce a setting value; raise ValueError on a bad key or value."""
    if key not in KNOWN_KEYS:
        raise ValueError(f"unknown setting '{key}' (known: {', '.join(KNOWN_KEYS)})")
    if key == "reflection.provider":
        if value.lower() not in _PROVIDERS:
            raise ValueError(f"provider must be one of: {', '.join(_PROVIDERS)}")
        return value.lower()
    if key == "reflection.timeout":
        try:
            return float(value)
        except ValueError:
            raise ValueError("timeout must be a number") from None
    if key == "reflection.max_tokens":
        try:
            return int(value)
        except ValueError:
            raise ValueError("max_tokens must be an integer") from None
    if key == "reflection.base_url" and not value.startswith(("http://", "https://")):
        raise ValueError("base_url must start with http:// or https://")
    return value


def mask_key(value: str) -> str:
    if not value:
        return ""
    return f"{value[:3]}...{value[-2:]}" if len(value) > 6 else "set"


def _source(env_names: tuple[str, ...], file_present: bool) -> str:
    if any(os.environ.get(n) for n in env_names):
        return "env"
    return "file" if file_present else "default"


def get_setting(key: str) -> str:
    """The resolved raw value of one setting (for ``config get``; key returned raw)."""
    if key == "machine_id":
        return resolve_machine_id()
    if key == "remote":
        return resolve_remote() or ""
    s = resolve_reflection_settings()
    table = {
        "reflection.provider": s.provider,
        "reflection.model": s.model,
        "reflection.base_url": s.base_url,
        "reflection.api_key": s.api_key,
        "reflection.timeout": str(s.timeout),
        "reflection.max_tokens": str(s.max_tokens),
    }
    if key in table:
        return table[key]
    raise ValueError(f"unknown setting '{key}'")


def settings_view() -> dict[str, Any]:
    """An effective-settings view with the api key masked (never the raw key)."""
    s = resolve_reflection_settings()
    block = _reflection_block()
    top = _store_config()
    return {
        "machine_id": {
            "value": resolve_machine_id(),
            "source": _source(("ANAMNESIS_MACHINE_ID",), "machine_id" in top),
        },
        "remote": {
            "value": resolve_remote() or "",
            "source": _source(("ANAMNESIS_GIT_REMOTE",), "remote" in top),
        },
        "reflection": {
            "provider": {
                "value": s.provider,
                "source": _source(("ANAMNESIS_REFLECTION_PROVIDER",), "provider" in block),
            },
            "model": {
                "value": s.model,
                "source": _source(("ANAMNESIS_REFLECTION_MODEL",), "model" in block),
            },
            "base_url": {
                "value": s.base_url,
                "source": _source(("ANAMNESIS_REFLECTION_BASE_URL",), "base_url" in block),
            },
            "timeout": {
                "value": s.timeout,
                "source": _source(("ANAMNESIS_REFLECTION_TIMEOUT",), "timeout" in block),
            },
            "max_tokens": {
                "value": s.max_tokens,
                "source": _source(("ANAMNESIS_REFLECTION_MAX_TOKENS",), "max_tokens" in block),
            },
            "api_key_set": bool(s.api_key),
            "api_key_preview": mask_key(s.api_key),
            "api_key_source": _source(
                ("ANAMNESIS_REFLECTION_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
                "api_key" in block,
            ),
        },
    }
