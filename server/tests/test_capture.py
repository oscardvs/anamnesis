import json

from anamnesis.capture import ParsedSession, parse_transcript


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
