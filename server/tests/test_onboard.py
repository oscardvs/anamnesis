from pathlib import Path

from anamnesis.onboard import (
    build_env,
    build_hooks,
    build_mcp_add_argv,
    build_mcp_remove_argv,
    detect_command,
    merge_hooks,
)


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


def _anamnesis_hooks():
    return build_hooks(["/bin/anamnesis"], {"ANAMNESIS_MACHINE_ID": "box"})


def test_merge_preserves_other_settings_keys():
    settings = {"model": "opus", "statusLine": {"type": "x"}}
    merged = merge_hooks(settings, _anamnesis_hooks())
    assert merged["model"] == "opus"
    assert merged["statusLine"] == {"type": "x"}
    assert "SessionStart" in merged["hooks"]


def test_merge_preserves_non_anamnesis_hooks():
    settings = {
        "hooks": {
            "PreToolUse": [{"hooks": [{"type": "command", "command": "/usr/bin/guard --check"}]}]
        }
    }
    merged = merge_hooks(settings, _anamnesis_hooks())
    assert merged["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "/usr/bin/guard --check"
    assert "SessionEnd" in merged["hooks"]


def test_merge_is_idempotent_does_not_duplicate():
    settings: dict = {}
    once = merge_hooks(settings, _anamnesis_hooks())
    twice = merge_hooks(once, _anamnesis_hooks())
    assert once == twice
    assert len(twice["hooks"]["SessionStart"]) == 2


def test_merge_drops_stale_anamnesis_group_in_shared_event():
    # an event that holds both an anamnesis group and a user group
    settings = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup",
                    "hooks": [{"type": "command", "command": "old anamnesis inject"}],
                },
                {
                    "matcher": "startup",
                    "hooks": [{"type": "command", "command": "/usr/bin/notify"}],
                },
            ]
        }
    }
    merged = merge_hooks(settings, _anamnesis_hooks())
    cmds = [h["command"] for g in merged["hooks"]["SessionStart"] for h in g["hooks"]]
    assert "old anamnesis inject" not in cmds
    assert "/usr/bin/notify" in cmds
    assert any(c.endswith("anamnesis inject") for c in cmds)


def test_build_mcp_add_argv_user_scope_env_and_command():
    argv = build_mcp_add_argv(
        ["/bin/anamnesis"],
        {"ANAMNESIS_MACHINE_ID": "box", "ANAMNESIS_GIT_REMOTE": "me@h:m.git"},
        "anamnesis",
    )
    assert argv[:7] == ["claude", "mcp", "add", "--scope", "user", "--transport", "stdio"]
    assert "--env" in argv and "ANAMNESIS_MACHINE_ID=box" in argv
    assert "ANAMNESIS_GIT_REMOTE=me@h:m.git" in argv
    sep = argv.index("--")
    assert argv[sep - 1] == "anamnesis"  # the server name precedes the separator
    assert argv[sep + 1 :] == ["/bin/anamnesis", "serve"]


def test_build_mcp_remove_argv():
    assert build_mcp_remove_argv("anamnesis") == [
        "claude",
        "mcp",
        "remove",
        "--scope",
        "user",
        "anamnesis",
    ]
