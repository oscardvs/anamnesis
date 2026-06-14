import io
import json

from anamnesis.cli import build_parser, cmd_inject, read_hook_payload, resolve_command
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
    store.write(type="semantic", title="global-pref", body="no em dashes",
                project="global", machine_id="m")
    store.write(type="procedural", title="proj-note", body="do the thing",
                project="p", machine_id="m")
    store.close()

    args = build_parser().parse_args(["inject", "--project", "p", "--k", "8"])
    rc = cmd_inject(args, {})
    out = capsys.readouterr().out
    assert rc == 0
    assert "global-pref" in out
    assert "proj-note" in out
