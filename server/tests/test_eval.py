"""Tests for the measurement harness (synthetic fixtures only)."""

from __future__ import annotations

from pathlib import Path

from anamnesis.eval import (
    EvalCase,
    RecallReport,
    WorkingSetReport,
    append_candidates,
    estimate_tokens,
    inject_working_set,
    load_eval_set,
    recall_at_k,
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


def test_recall_at_k_hits_top_result(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    m = store.write(
        type="semantic", title="WAL mode prevents lock conflicts", body="Use WAL.", project="p"
    )
    rep = recall_at_k(store, [EvalCase(query="WAL mode lock conflicts", relevant_ids=[m.id])], ks=(1, 3))
    assert rep.recall_at[1] == 1.0
    assert rep.recall_at[3] == 1.0
    assert rep.mrr == 1.0
    store.close()


def test_recall_at_k_counts_miss(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    store.write(type="semantic", title="Unrelated note", body="nothing here", project="p")
    rep = recall_at_k(
        store, [EvalCase(query="quantum entanglement teleportation", relevant_ids=["01NONE"])], ks=(1,)
    )
    assert rep.recall_at[1] == 0.0
    assert rep.mrr == 0.0
    store.close()


def test_recall_at_k_is_monotonic_in_k(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    # Two notes share the word "alpha"; the target is the less BM25-favored one.
    target = store.write(type="semantic", title="alpha beta", body="x", project="p")
    store.write(type="semantic", title="alpha alpha alpha", body="x", project="p")
    rep = recall_at_k(store, [EvalCase(query="alpha", relevant_ids=[target.id])], ks=(1, 3))
    assert rep.recall_at[3] >= rep.recall_at[1]
    store.close()


def test_recall_at_k_empty_cases(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    rep = recall_at_k(store, [], ks=(1, 5))
    assert rep.n_cases == 0
    assert rep.recall_at == {1: 0.0, 5: 0.0}
    assert rep.mrr == 0.0
    store.close()


def test_inject_working_set_drops_reflected_episodic(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    store.write(type="episodic", title="Session A", body="a" * 400, project="p", tags=["reflected"])
    store.write(type="episodic", title="Session B", body="b" * 400, project="q")
    ws = inject_working_set(store)
    assert ws.per_project["p"] == 0  # only a reflected episodic -> nothing injected
    assert ws.per_project["q"] > 0
    assert ws.corpus_tokens > 0
    store.close()


def test_inject_working_set_excludes_global_project(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    store.write(type="semantic", title="Global pref", body="x", project="global")
    store.write(type="semantic", title="Proj note", body="y", project="p")
    ws = inject_working_set(store)
    assert "global" not in ws.per_project
    assert "p" in ws.per_project


def test_inject_working_set_empty_store(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    ws = inject_working_set(store)
    assert ws.per_project == {}
    assert ws.mean_tokens == 0.0
    assert ws.median_tokens == 0.0
    assert ws.corpus_tokens == 0
    store.close()
