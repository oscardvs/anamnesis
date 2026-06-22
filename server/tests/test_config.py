import json
from pathlib import Path

from anamnesis.config import (
    resolve_claude_home,
    resolve_home,
    resolve_machine_id,
    resolve_remote,
)


def test_resolve_home_env_override_and_expanduser(monkeypatch):
    monkeypatch.setenv("ANAMNESIS_HOME", "~/somewhere")
    assert resolve_home() == Path.home() / "somewhere"


def test_resolve_home_default(monkeypatch):
    monkeypatch.delenv("ANAMNESIS_HOME", raising=False)
    assert resolve_home() == Path.home() / ".anamnesis"


def test_resolve_machine_id_override_and_nonempty(monkeypatch):
    monkeypatch.setenv("ANAMNESIS_MACHINE_ID", "desktop-amsterdam")
    assert resolve_machine_id() == "desktop-amsterdam"
    monkeypatch.delenv("ANAMNESIS_MACHINE_ID", raising=False)
    assert resolve_machine_id()


def test_resolve_remote_none_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path))  # empty store, no config file
    assert resolve_remote() is None


def test_resolve_remote_falls_back_to_store_config(monkeypatch, tmp_path):
    # The MCP server is launched (via .mcp.json) without inline env; the per-store
    # config.json lets it find the remote so an in-session memory_sync can push.
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"remote": "me@host:mem.git"}))
    assert resolve_remote() == "me@host:mem.git"


def test_resolve_remote_env_overrides_store_config(monkeypatch, tmp_path):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"remote": "from-file"}))
    monkeypatch.setenv("ANAMNESIS_GIT_REMOTE", "from-env")
    assert resolve_remote() == "from-env"


def test_resolve_machine_id_falls_back_to_store_config(monkeypatch, tmp_path):
    monkeypatch.delenv("ANAMNESIS_MACHINE_ID", raising=False)
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path))
    (tmp_path / "config.json").write_text(json.dumps({"machine_id": "configured-id"}))
    assert resolve_machine_id() == "configured-id"


def test_store_config_tolerates_missing_and_malformed(monkeypatch, tmp_path):
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path))
    assert resolve_remote() is None  # no config.json at all
    (tmp_path / "config.json").write_text("{ not json")
    assert resolve_remote() is None  # malformed config is ignored, not fatal


def test_resolve_claude_home_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "dotclaude"))
    assert resolve_claude_home() == tmp_path / "dotclaude"


def test_resolve_claude_home_default(monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert resolve_claude_home() == Path.home() / ".claude"


def test_server_reexports_resolvers_stay_importable():
    # Backward-compat: existing imports from anamnesis.server must keep working.
    from anamnesis.config import resolve_home as rc
    from anamnesis.server import resolve_home as rh

    assert rh is rc
