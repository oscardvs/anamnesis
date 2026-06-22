import io
import json

import pytest

from anamnesis.cli import (
    build_parser,
    cmd_backfill_provenance,
    cmd_capture,
    cmd_inject,
    cmd_migrate,
    cmd_reflect,
    cmd_reindex,
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


def test_cmd_capture_skips_trivial_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    transcript = tmp_path / "empty.jsonl"
    transcript.write_text("", encoding="utf-8")

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
    assert "skipped trivial session" in capsys.readouterr().out

    store = MemoryStore(root=tmp_path / "store")
    notes = store.list(project="p", type="episodic")
    store.close()
    assert notes == []


def test_resolve_command_parses_reindex():
    assert resolve_command(["reindex"]) == "reindex"


def test_cmd_reindex_rebuilds_index_from_markdown(tmp_path, monkeypatch, capsys):
    # The dashboard writes markdown directly, then triggers a reindex; this CLI
    # seam must rebuild the derived index from the markdown source of truth.
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    store = MemoryStore(root=tmp_path / "store")
    store.write(type="semantic", title="t", body="b", project="p", machine_id="m")
    store.close()

    # Simulate a fresh/stale index: drop index.db, keep the markdown.
    for suffix in ("", "-wal", "-shm"):
        p = tmp_path / "store" / f"index.db{suffix}"
        if p.exists():
            p.unlink()

    assert cmd_reindex() == 0
    out = capsys.readouterr().out
    assert "reindex" in out and "1" in out

    store = MemoryStore(root=tmp_path / "store")
    found = store.search("t", project="p")
    store.close()
    assert len(found) == 1


def test_main_dispatches_reindex(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    store = MemoryStore(root=tmp_path / "store")
    store.write(type="semantic", title="t", body="b", project="p", machine_id="m")
    store.close()
    assert main(["reindex"]) == 0
    assert "reindex" in capsys.readouterr().out


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


def test_main_dispatches_init_installs_hooks_and_syncs(tmp_path, monkeypatch):
    # the real (non --print) dispatch path: writes hooks to a temp CLAUDE_CONFIG_DIR
    # and does a local-only first sync. --no-mcp keeps it from touching the real `claude`.
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
            "--no-mcp",
        ]
    )
    assert rc == 0
    assert (tmp_path / "dotclaude" / "settings.json").exists()
    assert (tmp_path / "store" / "memory" / ".git").is_dir()


_NATIVE_NOTE = (
    "---\n"
    "name: a-note\n"
    'description: "A durable fact"\n'
    "metadata:\n"
    "  type: project\n"
    "---\n"
    "Body text.\n"
)


def _make_native(claude_home, slug="-home-user-repo"):
    mem_dir = claude_home / "projects" / slug / "memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "a-note.md").write_text(_NATIVE_NOTE, encoding="utf-8")


def test_main_dispatches_import_writes_native_notes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    claude = tmp_path / "claude"
    _make_native(claude)

    rc = main(["import", "--claude-home", str(claude), "--no-sync"])
    assert rc == 0
    assert "import:" in capsys.readouterr().out

    store = MemoryStore(root=tmp_path / "store")
    notes = store.list()
    store.close()
    assert len(notes) == 1
    assert notes[0].body == "Body text."
    assert notes[0].scope == "portable"


def test_sync_auto_imports_native_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    claude = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    _make_native(claude)

    assert main(["sync"]) == 0

    store = MemoryStore(root=tmp_path / "store")
    notes = store.list()
    store.close()
    assert any(n.body == "Body text." for n in notes)


def test_sync_skips_import_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    claude = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude))
    monkeypatch.setenv("ANAMNESIS_IMPORT_NATIVE", "0")
    _make_native(claude)

    assert main(["sync"]) == 0

    store = MemoryStore(root=tmp_path / "store")
    notes = store.list()
    store.close()
    assert notes == []


def test_init_parser_rejects_conflicting_flags():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["init", "--remote", "x", "--local-only"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["init", "--command", "x", "--uv-project", "y"])


def test_main_dispatches_dedup_dry_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    store = MemoryStore(root=tmp_path / "store")
    store.write(type="episodic", title="s", body="dup", project="x", machine_id="m")
    store.write(type="episodic", title="s", body="dup", project="y", machine_id="m")
    store.close()
    assert main(["dedup"]) == 0
    assert "1 duplicate(s) would be removed" in capsys.readouterr().out


def test_main_dispatches_dedup_apply(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    store = MemoryStore(root=tmp_path / "store")
    store.write(type="episodic", title="s", body="dup", project="x", machine_id="m")
    store.write(type="episodic", title="s", body="dup", project="y", machine_id="m")
    store.close()
    assert main(["dedup", "--apply", "--no-sync"]) == 0
    assert "removed 1 duplicate(s)" in capsys.readouterr().out
    store = MemoryStore(root=tmp_path / "store")
    total = store.stats().total
    store.close()
    assert total == 1


def test_cmd_backfill_provenance_dry_run_then_apply(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    store = MemoryStore(root=tmp_path / "store")
    mem = store.write(type="episodic", title="t", body="b", tags=["session", "session-end"])
    store.close()  # written as default human; tags say session

    dry = build_parser().parse_args(["backfill-provenance"])
    cmd_backfill_provenance(dry)
    assert "would change" in capsys.readouterr().out

    apply = build_parser().parse_args(["backfill-provenance", "--apply", "--no-sync"])
    cmd_backfill_provenance(apply)
    assert "rewrote 1" in capsys.readouterr().out

    store2 = MemoryStore(root=tmp_path / "store")
    assert store2.get(mem.id).prov_source == "session-end"
    store2.close()


def _seed_episodics(store, project, n):
    for i in range(n):
        store.write(
            type="episodic", title=f"s{i}", body="did work", project=project, tags=["session"]
        )


def test_cmd_reflect_dry_run_respects_threshold(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.setenv("ANAMNESIS_REFLECT_MIN_EPISODICS", "5")
    store = MemoryStore(root=tmp_path / "store")
    _seed_episodics(store, "big", 6)
    _seed_episodics(store, "small", 2)
    store.close()

    args = build_parser().parse_args(["reflect"])
    cmd_reflect(args)
    out = capsys.readouterr().out
    assert "big: 6 episodic(s) would be distilled" in out
    assert "small" not in out  # below threshold


def test_cmd_reflect_apply_unconfigured_reports(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.setenv("ANAMNESIS_REFLECT_MIN_EPISODICS", "1")
    monkeypatch.delenv("ANAMNESIS_REFLECTION_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = MemoryStore(root=tmp_path / "store")
    _seed_episodics(store, "p", 2)
    store.close()

    args = build_parser().parse_args(["reflect", "--apply", "--no-sync"])
    cmd_reflect(args)
    assert "no reflection provider configured" in capsys.readouterr().out


def test_cmd_reflect_apply_with_fake_reflector(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    monkeypatch.setenv("ANAMNESIS_REFLECT_MIN_EPISODICS", "1")
    store = MemoryStore(root=tmp_path / "store")
    _seed_episodics(store, "p", 2)
    store.close()

    from anamnesis.reflect import Reflector

    def fake():
        return Reflector(
            client=lambda system, user: '[{"type":"semantic","title":"T","body":"B"}]',
            model_label="deepseek/test",
        )

    monkeypatch.setattr("anamnesis.cli.make_reflector", fake)
    args = build_parser().parse_args(["reflect", "--apply", "--no-sync"])
    cmd_reflect(args)
    assert "distilled 2 episodic(s) -> 1 note(s)" in capsys.readouterr().out

    store = MemoryStore(root=tmp_path / "store")
    notes = store.list(project="p", type="semantic")
    assert len(notes) == 1 and notes[0].prov_source == "reflection"
    store.close()
