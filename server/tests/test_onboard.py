import json
from pathlib import Path

import pytest

from anamnesis.onboard import (
    InitOptions,
    build_env,
    build_hooks,
    build_mcp_add_argv,
    build_mcp_remove_argv,
    claude_dir,
    detect_command,
    merge_hooks,
    read_settings,
    run_init,
    write_settings,
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
    assert starts[1]["matcher"] == "startup|resume"
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


def test_merge_idempotent_for_non_anamnesis_command_form():
    # a --command override whose binary is not named "anamnesis"; idempotency must
    # still hold because our commands carry the inline ANAMNESIS_ env prefix.
    hooks = build_hooks(["python", "-m", "anam"], {"ANAMNESIS_MACHINE_ID": "box"})
    once = merge_hooks({}, hooks)
    twice = merge_hooks(once, hooks)
    assert once == twice
    assert len(twice["hooks"]["SessionStart"]) == 2
    assert len(twice["hooks"]["SessionEnd"]) == 1
    assert len(twice["hooks"]["PreCompact"]) == 1


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


def test_claude_dir_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cc"))
    assert claude_dir() == tmp_path / "cc"
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    assert claude_dir() == Path.home() / ".claude"


def test_read_settings_missing_or_empty_is_empty(tmp_path):
    assert read_settings(tmp_path / "nope.json") == {}
    (tmp_path / "empty.json").write_text("", encoding="utf-8")
    assert read_settings(tmp_path / "empty.json") == {}


def test_read_settings_rejects_non_object(tmp_path):
    p = tmp_path / "arr.json"
    p.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        read_settings(p)


def test_read_settings_rejects_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_settings(p)


def test_write_settings_backs_up_and_writes_atomically(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"old": True}), encoding="utf-8")
    write_settings(p, {"new": True})
    assert json.loads(p.read_text()) == {"new": True}
    assert json.loads((tmp_path / "settings.json.bak").read_text()) == {"old": True}


def test_write_settings_creates_parent(tmp_path):
    p = tmp_path / "cc" / "settings.json"
    write_settings(p, {"k": 1})
    assert json.loads(p.read_text()) == {"k": 1}


def _which_all_present(tmp_path):
    table = {
        "claude": "/usr/bin/claude",
        "anamnesis": str(tmp_path / "bin" / "anamnesis"),
        "uv": "/usr/bin/uv",
    }
    return lambda c: table.get(c)


def test_run_init_writes_hooks_registers_mcp_and_syncs(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "dotclaude"))
    calls: list[list[str]] = []

    opts = InitOptions(home=tmp_path / "store", machine_id="testbox", local_only=True, yes=True)
    rc = run_init(
        opts,
        prompt=lambda label, default: default,
        runner=lambda argv: calls.append(argv) or (0, ""),
        which=_which_all_present(tmp_path),
    )
    assert rc == 0

    settings = json.loads((tmp_path / "dotclaude" / "settings.json").read_text())
    cmds = [h["command"] for g in settings["hooks"]["SessionStart"] for h in g["hooks"]]
    assert any("anamnesis inject" in c for c in cmds)
    assert all("ANAMNESIS_MACHINE_ID=testbox" in c for c in cmds)

    assert any(argv[:3] == ["claude", "mcp", "add"] for argv in calls)  # claude mcp add ran
    assert (tmp_path / "store" / "memory" / ".git").is_dir()  # first sync inited the repo


def test_run_init_print_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "dotclaude"))
    opts = InitOptions(
        home=tmp_path / "store", machine_id="box", local_only=True, yes=True, print_only=True
    )
    rc = run_init(
        opts,
        prompt=lambda label, default: default,
        runner=lambda argv: (0, ""),
        which=_which_all_present(tmp_path),
    )
    assert rc == 0
    assert "plan" in capsys.readouterr().out.lower()
    assert not (tmp_path / "dotclaude" / "settings.json").exists()
    assert not (tmp_path / "store").exists()


def test_run_init_without_claude_prints_manual_mcp_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "dotclaude"))
    opts = InitOptions(home=tmp_path / "store", machine_id="box", local_only=True, yes=True)
    rc = run_init(
        opts,
        prompt=lambda label, default: default,
        runner=lambda argv: (0, ""),
        which=lambda c: None,  # nothing on PATH: no claude, no anamnesis, no uv
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "claude mcp add" in out  # manual fallback printed
    assert (tmp_path / "dotclaude" / "settings.json").exists()  # hooks still installed


def test_run_init_aborts_on_unparseable_settings(tmp_path, monkeypatch, capsys):
    cc = tmp_path / "dotclaude"
    cc.mkdir()
    (cc / "settings.json").write_text("{ not json", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cc))
    calls: list[list[str]] = []

    opts = InitOptions(home=tmp_path / "store", machine_id="box", local_only=True, yes=True)
    rc = run_init(
        opts,
        prompt=lambda label, default: default,
        runner=lambda argv: calls.append(argv) or (0, ""),
        which=_which_all_present(tmp_path),
    )
    assert rc == 1
    assert "not valid JSON" in capsys.readouterr().out
    assert calls == []  # aborted before registering the MCP server
    assert not (tmp_path / "store").exists()  # and before the first sync


def test_run_init_sync_failure_is_not_fatal(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "dotclaude"))
    opts = InitOptions(
        home=tmp_path / "store",
        machine_id="box",
        remote="/nonexistent/anam-memory.git",  # push will fail
        yes=True,
        no_mcp=True,
    )
    rc = run_init(
        opts,
        prompt=lambda label, default: default,
        runner=lambda argv: (0, ""),
        which=_which_all_present(tmp_path),
    )
    assert rc == 0  # a failed sync is a warning, not a crash
    assert "sync" in capsys.readouterr().out.lower()
    assert (tmp_path / "dotclaude" / "settings.json").exists()  # hooks still installed


def test_run_init_no_hooks_skips_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "dotclaude"))
    rc = run_init(
        InitOptions(
            home=tmp_path / "store",
            machine_id="box",
            local_only=True,
            yes=True,
            no_hooks=True,
            no_mcp=True,
        ),
        prompt=lambda label, default: default,
        runner=lambda argv: (0, ""),
        which=_which_all_present(tmp_path),
    )
    assert rc == 0
    assert not (tmp_path / "dotclaude" / "settings.json").exists()
    assert (tmp_path / "store" / "memory" / ".git").is_dir()  # sync still ran


def test_run_init_reports_mcp_add_failure_nonfatal(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "dotclaude"))
    rc = run_init(
        InitOptions(home=tmp_path / "store", machine_id="box", local_only=True, yes=True),
        prompt=lambda label, default: default,
        runner=lambda argv: (1, "boom") if "add" in argv else (0, ""),
        which=_which_all_present(tmp_path),
    )
    assert rc == 0  # an mcp add failure is reported, not fatal
    assert "mcp: add failed" in capsys.readouterr().out
    assert (tmp_path / "dotclaude" / "settings.json").exists()  # hooks still installed


def test_run_init_interactive_threads_prompted_values(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "dotclaude"))
    home = tmp_path / "picked-store"
    answers = {
        "store home": str(home),
        "machine id": "prompted-box",
        "sync remote": "",  # blank -> local-only
        "command form": "/custom/anamnesis",
    }

    def prompt(label, default):
        for key, val in answers.items():
            if label.startswith(key):
                return val
        return default

    rc = run_init(
        InitOptions(yes=False, no_mcp=True),  # interactive, skip mcp registration
        prompt=prompt,
        runner=lambda argv: (0, ""),
        which=_which_all_present(tmp_path),
    )
    assert rc == 0
    settings = json.loads((tmp_path / "dotclaude" / "settings.json").read_text())
    cmds = [h["command"] for g in settings["hooks"]["SessionStart"] for h in g["hooks"]]
    assert all("ANAMNESIS_MACHINE_ID=prompted-box" in c for c in cmds)
    # command-form override threaded through to hook commands
    assert any(c.endswith("/custom/anamnesis inject") for c in cmds)
    assert (home / "memory" / ".git").is_dir()  # store created at the prompted home
