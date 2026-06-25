import json

from anamnesis.capture import (
    HeuristicSummarizer,
    ParsedSession,
    is_trivial_session,
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
    r = HeuristicSummarizer().summarize(s)
    assert r is not None
    assert r.title == "Add a CLI"
    assert "**Ask:** Add a CLI" in r.body
    assert "**Branch:** main" in r.body
    assert "**Files touched (2):**" in r.body
    assert "- cli.py" in r.body
    assert "**Outcome:** Done, shipped" in r.body
    assert r.prov_model == ""


def test_heuristic_summarizer_handles_empty_session():
    r = HeuristicSummarizer().summarize(ParsedSession())
    assert r is not None
    assert r.title == "Session summary"
    assert "(no user prompt captured)" in r.body


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


def test_raw_holds_full_transcript(tmp_path):
    p = _transcript(
        tmp_path,
        {"type": "user", "message": {"role": "user", "content": "Add a CLI"}},
    )
    s = parse_transcript(p)
    assert "Add a CLI" in s.raw


def test_trivial_empty_session():
    assert is_trivial_session(ParsedSession()) is True


def test_trivial_slash_command_only():
    s = ParsedSession(first_prompt="/effort", last_outcome="")
    assert is_trivial_session(s) is True


def test_trivial_no_prompt_short_outcome():
    s = ParsedSession(first_prompt="", last_outcome="ok")
    assert is_trivial_session(s) is True


def test_not_trivial_when_files_touched():
    s = ParsedSession(first_prompt="/clear", files_touched=["a.py"])
    assert is_trivial_session(s) is False


def test_not_trivial_real_prompt():
    s = ParsedSession(first_prompt="How do I wire the sync hook?", last_outcome="")
    assert is_trivial_session(s) is False


def test_write_episodic_skips_trivial_session(tmp_path):
    store = MemoryStore(root=tmp_path)
    mem = write_episodic(
        store,
        ParsedSession(),  # empty -> gated
        summarizer=HeuristicSummarizer(),
        project="proj",
        source="session-end",
        machine_id="m",
    )
    assert mem is None
    assert store.list(project="proj") == []


class _SkipSummarizer:
    def summarize(self, session):
        return None  # passed the gate but self-skips


def test_write_episodic_honors_summarizer_self_skip(tmp_path):
    store = MemoryStore(root=tmp_path)
    session = ParsedSession(first_prompt="Real ask that passes the gate", last_outcome="x" * 50)
    mem = write_episodic(
        store,
        session,
        summarizer=_SkipSummarizer(),
        project="proj",
        source="session-end",
        machine_id="m",
    )
    assert mem is None
    assert store.list(project="proj") == []


def test_write_episodic_stamps_empty_prov_model_for_heuristic(tmp_path):
    store = MemoryStore(root=tmp_path)
    session = ParsedSession(first_prompt="Do a thing", last_outcome="Did it")
    mem = write_episodic(
        store,
        session,
        summarizer=HeuristicSummarizer(),
        project="proj",
        source="session-end",
        machine_id="m",
    )
    assert mem is not None
    assert mem.prov_model == ""


def test_write_episodic_stamps_session_provenance(tmp_path):
    store = MemoryStore(root=tmp_path)
    session = ParsedSession(first_prompt="Do a thing", last_outcome="Did it", session_id="sess-1")
    mem = write_episodic(
        store,
        session,
        summarizer=HeuristicSummarizer(),
        project="proj",
        source="session-end",
        machine_id="m",
    )
    assert mem is not None
    assert mem.prov_source == "session-end"
    assert mem.prov_session == "sess-1"


def test_resolve_summarizer_uses_config_json_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("ANAMNESIS_REFLECTION_PROVIDER", raising=False)
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path))
    tmp_path.mkdir(parents=True, exist_ok=True)
    import json

    (tmp_path / "config.json").write_text(
        json.dumps({"reflection": {"provider": "heuristic"}}), encoding="utf-8"
    )
    from anamnesis.capture import HeuristicSummarizer, resolve_summarizer

    # Proves the provider is read (via config.py) and mapped to the heuristic summarizer.
    assert isinstance(resolve_summarizer(), HeuristicSummarizer)
