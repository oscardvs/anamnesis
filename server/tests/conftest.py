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


@pytest.fixture(autouse=True)
def _isolate_anamnesis_home(tmp_path_factory, monkeypatch):
    """Never read the developer's real ``~/.anamnesis/config.json`` during tests.

    Config resolution is env > config.json > default; pointing ``ANAMNESIS_HOME``
    at an empty temp dir removes the file tier so provider/key tests that only
    clear the env vars see a truly unconfigured store (a test may override this
    by writing its own config.json under the temp home).
    """
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path_factory.mktemp("anamnesis_home")))
