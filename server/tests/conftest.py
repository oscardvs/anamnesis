"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _isolate_claude_home(tmp_path_factory, monkeypatch):
    """Never scan the developer's real ``~/.claude`` during the test suite.

    The sync path auto-imports Claude Code's native memory; point
    ``CLAUDE_CONFIG_DIR`` at an empty temp dir so that is a no-op unless a test
    sets up its own native-memory fixture (and overrides this).
    """
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path_factory.mktemp("claude_home")))
