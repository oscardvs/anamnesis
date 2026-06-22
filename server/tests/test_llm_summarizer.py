import json

import pytest

from anamnesis.capture import ParsedSession
from anamnesis.llm_summarizer import (
    LLMSummarizer,
    _parse_summary,
    _truncate_tool_results,
    _window,
)


def _client_returning(text):
    def call(system, user):
        return text

    return call


def _raw_with_prompt(text="Implement the reflection summarizer"):
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n"


def test_window_truncates_long_text():
    out = _window("a" * 100, max_chars=40)
    assert len(out) < 100
    assert "truncated" in out


def test_window_keeps_short_text():
    assert _window("short", max_chars=40) == "short"


def test_parse_summary_plain_json():
    skip, title, body = _parse_summary('{"skip": false, "title": "T", "body": "B"}')
    assert (skip, title, body) == (False, "T", "B")


def test_parse_summary_fenced_json():
    skip, title, body = _parse_summary('```json\n{"skip": true, "title": "", "body": ""}\n```')
    assert skip is True


def test_parse_summary_rejects_nonjson():
    with pytest.raises(ValueError):
        _parse_summary("not json at all")


def test_truncate_tool_results_caps_blob():
    raw = json.dumps(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "content": "X" * 5000}],
            },
        }
    )
    out = _truncate_tool_results(raw, cap=100)
    assert "X" * 5000 not in out
    assert "truncated" in out


def test_summarize_happy_path_adds_footer():
    summ = LLMSummarizer(
        client=_client_returning('{"skip": false, "title": "Did X", "body": "Built X."}'),
        model_label="deepseek/test-model",
    )
    session = ParsedSession(first_prompt="do x", last_outcome="done", raw=_raw_with_prompt())
    result = summ.summarize(session)
    assert result is not None
    title, body = result
    assert title == "Did X"
    assert "Built X." in body
    assert "deepseek/test-model" in body


def test_summarize_self_skip_returns_none():
    summ = LLMSummarizer(
        client=_client_returning('{"skip": true, "title": "", "body": ""}'),
        model_label="deepseek/test-model",
    )
    assert summ.summarize(ParsedSession(first_prompt="hi", raw=_raw_with_prompt())) is None


def test_summarize_falls_back_to_heuristic_on_client_error():
    def boom(system, user):
        raise TimeoutError("network down")

    summ = LLMSummarizer(client=boom, model_label="deepseek/test-model")
    session = ParsedSession(
        first_prompt="Add a CLI", last_outcome="Shipped it", raw=_raw_with_prompt()
    )
    result = summ.summarize(session)
    assert result is not None
    title, body = result
    assert "**Ask:** Add a CLI" in body  # heuristic body, not the LLM footer
    assert "deepseek/test-model" not in body


def test_summarize_falls_back_on_unparseable_json():
    summ = LLMSummarizer(
        client=_client_returning("the model rambled without JSON"),
        model_label="deepseek/test-model",
    )
    session = ParsedSession(
        first_prompt="Add a CLI", last_outcome="Shipped it", raw=_raw_with_prompt()
    )
    result = summ.summarize(session)
    assert result is not None
    _, body = result
    assert "**Ask:** Add a CLI" in body


def test_summarize_redacts_before_sending():
    captured = {}

    def spy(system, user):
        captured["user"] = user
        return '{"skip": false, "title": "T", "body": "B"}'

    raw = json.dumps({"type": "user", "message": {"content": "key sk-ABCD1234abcd5678efgh here"}})
    summ = LLMSummarizer(client=spy, model_label="deepseek/test-model")
    summ.summarize(ParsedSession(first_prompt="x", last_outcome="y", raw=raw))
    assert "sk-ABCD1234abcd5678efgh" not in captured["user"]
    assert "[REDACTED]" in captured["user"]
