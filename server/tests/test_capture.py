import json

from anamnesis.capture import (
    HeuristicSummarizer,
    ParsedSession,
    parse_transcript,
    resolve_summarizer,
    write_episodic,
)
from anamnesis.store import MemoryStore


def _line(obj):
    return json.dumps(obj)


def _transcript(tmp_path, *events):
    p = tmp_path / "transcript.jsonl"
    p.write_text("\n".join(_line(e) for e in events) + "\n", encoding="utf-8")
    return p


def test_parse_extracts_prompt_files_outcome_and_context(tmp_path):
    p = _transcript(
        tmp_path,
        {
            "type": "user",
            "cwd": "/home/x/proj",
            "gitBranch": "main",
            "sessionId": "s1",
            "message": {"role": "user", "content": "Add a CLI"},
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": "hmm"},
                    {"type": "text", "text": "Working on it"},
                    {
                        "type": "tool_use",
                        "name": "Edit",
                        "input": {
                            "file_path": "/home/x/proj/cli.py",
                            "old_string": "a",
                            "new_string": "b",
                        },
                    },
                ],
            },
        },
        {
            "type": "user",
            "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]},
        },
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Write",
                        "input": {"file_path": "/home/x/proj/new.py", "content": "x"},
                    },
                    {"type": "text", "text": "Done, shipped the CLI"},
                ],
            },
        },
    )
    s = parse_transcript(p)
    assert s.first_prompt == "Add a CLI"
    assert s.last_outcome == "Done, shipped the CLI"
    assert s.files_touched == ["/home/x/proj/cli.py", "/home/x/proj/new.py"]
    assert s.git_branch == "main"
    assert s.cwd == "/home/x/proj"
    assert s.session_id == "s1"


def test_parse_tolerates_garbage_and_block_content(tmp_path):
    ev = {"type": "user", "message": {"content": [{"type": "text", "text": "block prompt"}]}}
    p = tmp_path / "t.jsonl"
    p.write_text("not json\n" + _line(ev) + "\n" + "{bad}\n", encoding="utf-8")
    s = parse_transcript(p)
    assert s.first_prompt == "block prompt"


def test_parse_skips_meta_user_events(tmp_path):
    p = _transcript(
        tmp_path,
        {"type": "user", "isMeta": True, "message": {"content": "meta noise"}},
        {"type": "user", "message": {"content": "real ask"}},
    )
    assert parse_transcript(p).first_prompt == "real ask"


def test_parse_missing_file_returns_empty_session(tmp_path):
    s = parse_transcript(tmp_path / "nope.jsonl")
    assert s == ParsedSession()


def test_heuristic_summarizer_builds_title_and_body():
    s = ParsedSession(
        first_prompt="Add a CLI\nwith subcommands",
        last_outcome="Done, shipped",
        files_touched=["cli.py", "inject.py"],
        git_branch="main",
    )
    title, body = HeuristicSummarizer().summarize(s)
    assert title == "Add a CLI"  # first line of the ask, trimmed
    assert "**Ask:** Add a CLI" in body
    assert "**Branch:** main" in body
    assert "**Files touched (2):**" in body
    assert "- cli.py" in body
    assert "**Outcome:** Done, shipped" in body


def test_heuristic_summarizer_handles_empty_session():
    title, body = HeuristicSummarizer().summarize(ParsedSession())
    assert title == "Session summary"
    assert "(no user prompt captured)" in body


def test_resolve_summarizer_defaults_to_heuristic(monkeypatch):
    monkeypatch.delenv("ANAMNESIS_REFLECTION_PROVIDER", raising=False)
    assert isinstance(resolve_summarizer(), HeuristicSummarizer)
    monkeypatch.setenv("ANAMNESIS_REFLECTION_PROVIDER", "some-future-model")
    assert isinstance(resolve_summarizer(), HeuristicSummarizer)


def test_write_episodic_persists_with_source_tag(tmp_path):
    store = MemoryStore(root=tmp_path)
    session = ParsedSession(first_prompt="Do a thing", last_outcome="Did it")
    mem = write_episodic(
        store,
        session,
        summarizer=HeuristicSummarizer(),
        project="proj",
        source="precompact",
        machine_id="desktop",
    )
    assert mem.type == "episodic"
    assert mem.project == "proj"
    assert mem.machine_id == "desktop"
    assert "precompact" in mem.tags
    assert mem.id in [x.id for x in store.list(project="proj")]
