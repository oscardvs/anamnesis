import io
import json

from anamnesis.cli import (
    build_parser,
    cmd_capture,
    cmd_inject,
    cmd_migrate,
    cmd_status,
    main,
    read_hook_payload,
    resolve_command,
)
from anamnesis.store import MemoryStore


def test_resolve_command_defaults_to_serve():
    assert resolve_command([]) == "serve"


def test_resolve_command_parses_subcommands():
    for name in ("serve", "sync", "status", "inject", "capture"):
        assert resolve_command([name]) == name


def test_read_hook_payload_parses_piped_json(monkeypatch):
    stdin = io.StringIO(json.dumps({"cwd": "/x", "transcript_path": "/t.jsonl"}))
    stdin.isatty = lambda: False  # type: ignore[method-assign]
    monkeypatch.setattr("sys.stdin", stdin)
    assert read_hook_payload() == {"cwd": "/x", "transcript_path": "/t.jsonl"}


def test_read_hook_payload_empty_when_tty(monkeypatch):
    stdin = io.StringIO("")
    stdin.isatty = lambda: True  # type: ignore[method-assign]
    monkeypatch.setattr("sys.stdin", stdin)
    assert read_hook_payload() == {}


def test_build_parser_has_inject_and_capture_options():
    args = build_parser().parse_args(["inject", "--project", "p", "--k", "3"])
    assert args.command == "inject" and args.project == "p" and args.k == 3
    args = build_parser().parse_args(["capture", "--source", "precompact", "--no-sync"])
    assert args.command == "capture" and args.source == "precompact" and args.no_sync is True


def test_cmd_inject_prints_project_and_global_notes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    store = MemoryStore(root=tmp_path / "store")
    store.write(
        type="semantic", title="global-pref", body="no em dashes", project="global", machine_id="m"
    )
    store.write(
        type="procedural", title="proj-note", body="do the thing", project="p", machine_id="m"
    )
    store.close()

    args = build_parser().parse_args(["inject", "--project", "p", "--k", "8"])
    rc = cmd_inject(args, {})
    out = capsys.readouterr().out
    assert rc == 0
    assert "global-pref" in out
    assert "proj-note" in out


def test_cmd_capture_writes_episodic_note_no_sync(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    transcript = tmp_path / "t.jsonl"
    ev = {"type": "user", "cwd": str(tmp_path), "message": {"content": "Build the hooks"}}
    transcript.write_text(json.dumps(ev) + "\n", encoding="utf-8")

    args = build_parser().parse_args(
        [
            "capture",
            "--transcript",
            str(transcript),
            "--project",
            "p",
            "--source",
            "session-end",
            "--no-sync",
        ]
    )
    rc = cmd_capture(args, {})
    assert rc == 0
    assert "wrote episodic note" in capsys.readouterr().out

    store = MemoryStore(root=tmp_path / "store")
    notes = store.list(project="p", type="episodic")
    store.close()
    assert len(notes) == 1
    assert notes[0].title == "Build the hooks"
    assert "session-end" in notes[0].tags


def test_cmd_status_reports_counts(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    store = MemoryStore(root=tmp_path / "store")
    store.write(type="semantic", title="t", body="b", project="p", machine_id="m")
    store.close()
    assert cmd_status() == 0
    assert "notes: 1" in capsys.readouterr().out


def test_main_dispatches_status(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    assert main(["status"]) == 0
    assert "store:" in capsys.readouterr().out


def test_main_sync_without_remote_commits_locally(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    store = MemoryStore(root=tmp_path / "store")
    store.write(type="semantic", title="t", body="b", project="p", machine_id="m")
    store.close()
    assert main(["sync"]) == 0
    assert "sync:" in capsys.readouterr().out


def test_cmd_migrate_dry_run_lists_changes_without_writing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    store = MemoryStore(root=tmp_path / "store")
    store.write(type="semantic", title="t", body="b", project="old-key", machine_id="m")
    store.close()
    map_file = tmp_path / "map.json"
    map_file.write_text(
        json.dumps({"projects": {"old-key": "new-key"}, "notes": {}}), encoding="utf-8"
    )

    args = build_parser().parse_args(["migrate", "--map", str(map_file)])
    assert cmd_migrate(args) == 0
    assert "1 note(s) would change" in capsys.readouterr().out

    store = MemoryStore(root=tmp_path / "store")
    assert store.list(project="old-key") and not store.list(project="new-key")  # nothing written
    store.close()


def test_cmd_migrate_apply_rewrites_and_reindexes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    store = MemoryStore(root=tmp_path / "store")
    store.write(type="semantic", title="t", body="b", project="old-key", machine_id="m")
    store.close()
    map_file = tmp_path / "map.json"
    map_file.write_text(
        json.dumps({"projects": {"old-key": "new-key"}, "notes": {}}), encoding="utf-8"
    )

    args = build_parser().parse_args(["migrate", "--map", str(map_file), "--apply", "--no-sync"])
    assert cmd_migrate(args) == 0
    assert "applied 1 change(s)" in capsys.readouterr().out

    store = MemoryStore(root=tmp_path / "store")
    assert not store.list(project="old-key")
    moved = store.list(project="new-key")
    store.close()
    assert len(moved) == 1 and moved[0].title == "t"


def test_main_dispatches_migrate_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    store = MemoryStore(root=tmp_path / "store")
    store.write(type="semantic", title="t", body="b", project="old-key", machine_id="m")
    store.close()
    map_file = tmp_path / "map.json"
    map_file.write_text(json.dumps({"projects": {"old-key": "new-key"}}), encoding="utf-8")
    assert main(["migrate", "--map", str(map_file)]) == 0
    assert "would change" in capsys.readouterr().out


def test_build_parser_has_init_options():
    args = build_parser().parse_args(
        ["init", "--machine-id", "box", "--local-only", "--yes", "--print", "--no-mcp"]
    )
    assert args.command == "init"
    assert args.machine_id == "box"
    assert args.local_only is True
    assert args.yes is True
    assert args.print_plan is True
    assert args.no_mcp is True


def test_main_dispatches_init_print_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "dotclaude"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    rc = main(
        [
            "init",
            "--home",
            str(tmp_path / "store"),
            "--machine-id",
            "box",
            "--local-only",
            "--yes",
            "--print",
            "--no-mcp",
        ]
    )
    assert rc == 0
    assert "plan" in capsys.readouterr().out.lower()
    assert not (tmp_path / "dotclaude" / "settings.json").exists()
