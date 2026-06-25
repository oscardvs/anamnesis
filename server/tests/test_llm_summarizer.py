import json

import pytest

from anamnesis.capture import HeuristicSummarizer, ParsedSession, resolve_summarizer
from anamnesis.config import ReflectionSettings
from anamnesis.llm_summarizer import (
    LLMSummarizer,
    _parse_summary,
    _truncate_tool_results,
    _window,
    make_llm_summarizer,
    resolve_reflection_config,
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


def test_summarize_happy_path_records_prov_model():
    summ = LLMSummarizer(
        client=_client_returning('{"skip": false, "title": "Did X", "body": "Built X."}'),
        model_label="deepseek/test-model",
    )
    session = ParsedSession(first_prompt="do x", last_outcome="done", raw=_raw_with_prompt())
    result = summ.summarize(session)
    assert result is not None
    assert result.title == "Did X"
    assert "Built X." in result.body
    assert result.prov_model == "deepseek/test-model"
    assert "_summarized by" not in result.body  # footer removed; prov_model carries it


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
    assert "**Ask:** Add a CLI" in result.body  # heuristic body
    assert result.prov_model == ""  # honest: a fallback note is heuristic


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
    assert "**Ask:** Add a CLI" in result.body
    assert result.prov_model == ""


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


def _set_full_config(monkeypatch):
    monkeypatch.setenv("ANAMNESIS_REFLECTION_PROVIDER", "deepseek")
    monkeypatch.setenv("ANAMNESIS_REFLECTION_MODEL", "deepseek-test")
    monkeypatch.setenv("ANAMNESIS_REFLECTION_BASE_URL", "https://example.invalid")
    monkeypatch.delenv("ANAMNESIS_REFLECTION_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")


def _clear_keys(monkeypatch):
    monkeypatch.setenv("ANAMNESIS_REFLECTION_PROVIDER", "deepseek")
    monkeypatch.delenv("ANAMNESIS_REFLECTION_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_resolve_reflection_config_reads_env(monkeypatch):
    _set_full_config(monkeypatch)
    cfg = resolve_reflection_config()
    assert cfg.provider == "deepseek"
    assert cfg.model == "deepseek-test"
    assert cfg.base_url == "https://example.invalid"
    assert cfg.api_key == "sk-test-key"


def test_make_llm_summarizer_falls_back_without_key(monkeypatch):
    _clear_keys(monkeypatch)
    assert isinstance(make_llm_summarizer(), HeuristicSummarizer)


def test_make_llm_summarizer_builds_when_configured(monkeypatch):
    _set_full_config(monkeypatch)
    assert isinstance(make_llm_summarizer(), LLMSummarizer)


def test_resolve_summarizer_deepseek_when_configured(monkeypatch):
    _set_full_config(monkeypatch)
    assert isinstance(resolve_summarizer(), LLMSummarizer)


def test_resolve_summarizer_deepseek_falls_back_unconfigured(monkeypatch):
    _clear_keys(monkeypatch)
    assert isinstance(resolve_summarizer(), HeuristicSummarizer)


def test_resolve_reflection_config_reads_config_json(tmp_path, monkeypatch):
    for var in (
        "ANAMNESIS_REFLECTION_PROVIDER",
        "ANAMNESIS_REFLECTION_MODEL",
        "ANAMNESIS_REFLECTION_BASE_URL",
        "ANAMNESIS_REFLECTION_API_KEY",
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path))
    (tmp_path).mkdir(parents=True, exist_ok=True)
    import json

    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "reflection": {
                    "provider": "deepseek",
                    "model": "m",
                    "base_url": "https://x",
                    "api_key": "sk-cfg",
                }
            }
        ),
        encoding="utf-8",
    )
    from anamnesis.llm_summarizer import resolve_reflection_config

    cfg = resolve_reflection_config()
    assert cfg.provider == "deepseek"
    assert cfg.api_key == "sk-cfg"


def _settings(**kw):
    base = dict(
        provider="deepseek",
        model="m",
        base_url="https://x",
        api_key="sk",
        timeout=30.0,
        max_tokens=120000,
    )
    base.update(kw)
    return ReflectionSettings(**base)


def test_ping_reflection_heuristic_short_circuits():
    from anamnesis.llm_summarizer import ping_reflection

    ok, msg = ping_reflection(_settings(provider="heuristic"))
    assert ok is True
    assert "heuristic" in msg


def test_ping_reflection_ok_with_fake_client():
    from anamnesis.llm_summarizer import ping_reflection

    def factory(base_url, api_key, model, timeout):
        return lambda system, user: "ok"

    ok, msg = ping_reflection(_settings(), client_factory=factory)
    assert ok is True


def test_ping_reflection_reports_failure():
    from anamnesis.llm_summarizer import ping_reflection

    def factory(base_url, api_key, model, timeout):
        def call(system, user):
            raise RuntimeError("401 unauthorized")

        return call

    ok, msg = ping_reflection(_settings(), client_factory=factory)
    assert ok is False
    assert "401" in msg


def test_ping_reflection_incomplete_config():
    from anamnesis.llm_summarizer import ping_reflection

    ok, msg = ping_reflection(_settings(api_key=""))
    assert ok is False
    assert "incomplete" in msg
