from pathlib import Path

from anamnesis.onboard import build_env, build_hooks, detect_command


def test_detect_prefers_explicit_command_override():
    base = detect_command(override_command="/opt/anamnesis serve-wrap", which=lambda c: None)
    assert base == ["/opt/anamnesis", "serve-wrap"]


def test_detect_uv_project_override_builds_uv_run():
    base = detect_command(
        override_uv_project="/home/x/anamnesis/server", which=lambda c: "/usr/bin/uv"
    )
    assert base[:3] == ["/usr/bin/uv", "run", "--project"]
    assert base[3] == str(Path("/home/x/anamnesis/server").resolve())
    assert base[-1] == "anamnesis"


def test_detect_uses_installed_anamnesis_on_path():
    base = detect_command(
        which=lambda c: "/home/x/.local/bin/anamnesis" if c == "anamnesis" else None
    )
    assert base == ["/home/x/.local/bin/anamnesis"]


def test_detect_falls_back_to_uv_run_project_when_not_installed():
    base = detect_command(which=lambda c: "/usr/bin/uv" if c == "uv" else None)
    assert base[:2] == ["/usr/bin/uv", "run"]
    assert base[-1] == "anamnesis"
    # the discovered server dir is the package's checkout root (contains pyproject.toml)
    assert (Path(base[3]) / "pyproject.toml").is_file()


def test_detect_uv_project_override_uses_bare_uv_when_not_on_path():
    base = detect_command(override_uv_project="/home/x/anamnesis/server", which=lambda c: None)
    assert base[0] == "uv"
    assert base[-1] == "anamnesis"


def test_build_env_machine_id_always_present():
    env = build_env(machine_id="box", remote=None, home=None)
    assert env == {"ANAMNESIS_MACHINE_ID": "box"}


def test_build_env_includes_remote_and_home_when_given():
    env = build_env(machine_id="box", remote="me@host:mem.git", home=Path("/data/anam"))
    assert env["ANAMNESIS_GIT_REMOTE"] == "me@host:mem.git"
    assert env["ANAMNESIS_HOME"] == "/data/anam"


def test_build_hooks_has_four_commands_with_inline_env():
    base = ["/bin/anamnesis"]
    env = {"ANAMNESIS_MACHINE_ID": "box", "ANAMNESIS_GIT_REMOTE": "me@host:mem.git"}
    hooks = build_hooks(base, env)

    starts = hooks["SessionStart"]
    inject = starts[0]["hooks"][0]
    sync = starts[1]["hooks"][0]
    assert starts[0]["matcher"] == "startup|resume|clear"
    assert inject["command"].endswith("/bin/anamnesis inject")
    assert inject["timeout"] == 15
    assert inject["command"].startswith("ANAMNESIS_MACHINE_ID=box ")
    assert "ANAMNESIS_GIT_REMOTE=me@host:mem.git" in inject["command"]
    assert sync["async"] is True
    assert sync["command"].endswith("anamnesis sync")

    end = hooks["SessionEnd"][0]["hooks"][0]
    assert end["command"].endswith("anamnesis capture")
    assert end["timeout"] == 120

    pre = hooks["PreCompact"][0]["hooks"][0]
    assert pre["command"].endswith("anamnesis capture --source precompact --no-sync")
    assert pre["timeout"] == 60


def test_build_hooks_quotes_values_with_spaces():
    hooks = build_hooks(["/bin/anamnesis"], {"ANAMNESIS_MACHINE_ID": "my box"})
    cmd = hooks["SessionStart"][0]["hooks"][0]["command"]
    assert "ANAMNESIS_MACHINE_ID='my box'" in cmd
