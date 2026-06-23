"""Tests for the measurement harness (synthetic fixtures only)."""

from __future__ import annotations

from pathlib import Path

from anamnesis.eval import (
    EvalCase,
    append_candidates,
    estimate_tokens,
    load_eval_set,
    save_eval_set,
)
from anamnesis.store import MemoryStore


def test_estimate_tokens_empty_is_zero():
    assert estimate_tokens("") == 0


def test_estimate_tokens_four_chars_is_one_token():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_estimate_tokens_is_monotonic():
    assert estimate_tokens("a" * 100) >= estimate_tokens("a" * 40)


def test_eval_set_round_trip(tmp_path: Path):
    path = tmp_path / "eval.jsonl"
    cases = [
        EvalCase(query="q1", relevant_ids=["a"], note_titles=["A"], approved=True, source="human"),
        EvalCase(query="q2", relevant_ids=["b"], approved=False, source="llm:x"),
    ]
    save_eval_set(path, cases)
    loaded, warnings = load_eval_set(path, include_unreviewed=True)
    assert [c.query for c in loaded] == ["q1", "q2"]
    assert loaded[0].relevant_ids == ["a"]
    assert warnings == []


def test_load_eval_set_filters_unapproved_by_default(tmp_path: Path):
    path = tmp_path / "eval.jsonl"
    save_eval_set(
        path,
        [
            EvalCase(query="keep", relevant_ids=["a"], approved=True),
            EvalCase(query="drop", relevant_ids=["b"], approved=False),
        ],
    )
    loaded, warnings = load_eval_set(path)
    assert [c.query for c in loaded] == ["keep"]
    assert any("unreviewed" in w for w in warnings)


def test_load_eval_set_warns_on_stale_id_and_refreshes_titles(tmp_path: Path):
    store = MemoryStore(tmp_path / "store")
    m = store.write(type="semantic", title="Real Title", body="b", project="p")
    path = tmp_path / "eval.jsonl"
    save_eval_set(
        path,
        [EvalCase(query="q", relevant_ids=[m.id, "01MISSING"], note_titles=["stale"], approved=True)],
    )
    loaded, warnings = load_eval_set(path, store=store)
    assert loaded[0].note_titles == ["Real Title"]
    assert any("01MISSING" in w for w in warnings)
    store.close()


def test_append_candidates_skips_existing_query(tmp_path: Path):
    path = tmp_path / "eval.jsonl"
    save_eval_set(path, [EvalCase(query="dup", relevant_ids=["a"], approved=True)])
    added = append_candidates(
        path,
        [
            EvalCase(query="dup", relevant_ids=["a"], approved=False),
            EvalCase(query="new", relevant_ids=["b"], approved=False),
        ],
    )
    assert added == 1
    loaded, _ = load_eval_set(path, include_unreviewed=True)
    assert [c.query for c in loaded] == ["dup", "new"]
