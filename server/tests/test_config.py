from pathlib import Path

from anamnesis.config import resolve_home, resolve_machine_id, resolve_remote


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


def test_resolve_remote_none_when_unset(monkeypatch):
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    assert resolve_remote() is None


def test_server_reexports_resolvers_stay_importable():
    # Backward-compat: existing imports from anamnesis.server must keep working.
    from anamnesis.config import resolve_home as rc
    from anamnesis.server import resolve_home as rh

    assert rh is rc
