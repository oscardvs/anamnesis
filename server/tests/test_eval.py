"""Tests for the measurement harness (synthetic fixtures only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from anamnesis.eval import (
    BaselineReport,
    EvalCase,
    ExperimentReport,
    append_candidates,
    baseline_to_dict,
    build_eval_candidates,
    estimate_tokens,
    inject_working_set,
    load_eval_set,
    recall_at_k,
    render_baseline,
    render_experiment,
    run_baseline,
    run_reflection_experiment,
    sandbox_store,
    save_eval_set,
)
from anamnesis.reflect import Reflector
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
        [
            EvalCase(
                query="q", relevant_ids=[m.id, "01MISSING"], note_titles=["stale"], approved=True
            )
        ],
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
    rep = recall_at_k(
        store, [EvalCase(query="WAL mode lock conflicts", relevant_ids=[m.id])], ks=(1, 3)
    )
    assert rep.recall_at[1] == 1.0
    assert rep.recall_at[3] == 1.0
    assert rep.mrr == 1.0
    store.close()


def test_recall_at_k_counts_miss(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    store.write(type="semantic", title="Unrelated note", body="nothing here", project="p")
    rep = recall_at_k(
        store,
        [EvalCase(query="quantum entanglement teleportation", relevant_ids=["01NONE"])],
        ks=(1,),
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
    store.close()


def test_inject_working_set_empty_store(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    ws = inject_working_set(store)
    assert ws.per_project == {}
    assert ws.mean_tokens == 0.0
    assert ws.median_tokens == 0.0
    assert ws.corpus_tokens == 0
    store.close()


def test_build_eval_candidates_one_query_per_note(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    a = store.write(type="semantic", title="Note A", body="body a", project="p")
    b = store.write(type="procedural", title="Note B", body="body b", project="q")

    def client(system: str, user: str) -> str:
        return '{"query": "paraphrased question"}'

    cases = build_eval_candidates(store, client, "fake/model", n=10)
    assert len(cases) == 2
    assert all(c.approved is False for c in cases)
    assert all(c.source == "llm:fake/model" for c in cases)
    assert {c.relevant_ids[0] for c in cases} == {a.id, b.id}
    store.close()


def test_build_eval_candidates_redacts_secrets(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    store.write(type="semantic", title="Creds", body="key sk-SECRETVALUE123456 here", project="p")
    captured: list[str] = []

    def client(system: str, user: str) -> str:
        captured.append(user)
        return '{"query": "q"}'

    build_eval_candidates(store, client, "fake/model")
    assert "sk-SECRETVALUE123456" not in captured[0]
    assert "[REDACTED]" in captured[0]
    store.close()


def test_build_eval_candidates_raises_on_bad_json(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    store.write(type="semantic", title="Note", body="b", project="p")

    def client(system: str, user: str) -> str:
        return "not json at all"

    with pytest.raises(ValueError):
        build_eval_candidates(store, client, "fake/model")
    store.close()


def test_sandbox_store_copies_and_isolates(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    m = store.write(type="semantic", title="Orig", body="b", project="p")
    with sandbox_store(store) as sandbox:
        assert sandbox.root != store.root
        assert sandbox.get(m.id).title == "Orig"  # copy has the note
        sandbox.write(type="semantic", title="Sandbox only", body="b2", project="p")
    # The live store is untouched by the sandbox write.
    assert store.stats().total == 1
    store.close()


def test_sandbox_store_cleans_up(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    store.write(type="semantic", title="Orig", body="b", project="p")
    captured_root = None
    with sandbox_store(store) as sandbox:
        captured_root = sandbox.root
        assert captured_root.exists()
    assert not captured_root.exists()
    store.close()


def test_run_baseline_combines_recall_and_working_set(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    m = store.write(type="semantic", title="alpha topic", body="content", project="p")
    report = run_baseline(store, [EvalCase(query="alpha topic", relevant_ids=[m.id])], ks=(1, 3))
    assert report.recall.recall_at[1] == 1.0
    assert "p" in report.working_set.per_project
    assert isinstance(report, BaselineReport)
    store.close()


def test_render_baseline_is_readable(tmp_path: Path):
    store = MemoryStore(tmp_path / "s")
    m = store.write(type="semantic", title="alpha topic", body="content", project="p")
    text = render_baseline(
        run_baseline(store, [EvalCase(query="alpha topic", relevant_ids=[m.id])], ks=(1,))
    )
    assert "recall@1" in text
    assert "working set" in text
    store.close()


def test_baseline_to_dict_is_json_serializable(tmp_path: Path):
    import json as _json

    store = MemoryStore(tmp_path / "s")
    m = store.write(type="semantic", title="alpha topic", body="content", project="p")
    d = baseline_to_dict(
        run_baseline(store, [EvalCase(query="alpha topic", relevant_ids=[m.id])], ks=(1,))
    )
    _json.dumps(d)  # must not raise
    assert d["recall"]["recall_at"]["1"] == 1.0
    store.close()


def _fake_reflector(note_type: str = "semantic") -> Reflector:
    def client(system: str, user: str) -> str:
        return f'[{{"type": "{note_type}", "title": "Distilled", "body": "durable knowledge"}}]'

    return Reflector(client=client, model_label="fake/model")


def test_experiment_shrinks_inject_and_preserves_recall(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ANAMNESIS_REFLECT_MIN_EPISODICS", "2")
    store = MemoryStore(tmp_path / "s")
    # A semantic note the eval query targets (recall should survive reflection).
    target = store.write(type="semantic", title="WAL lock topic", body="x", project="p")
    # Enough verbose episodics to meet the threshold, so reflection drops them from inject.
    for i in range(3):
        store.write(type="episodic", title=f"Session {i}", body="chatter " * 80, project="p")
    cases = [EvalCase(query="WAL lock topic", relevant_ids=[target.id])]
    before_total = store.stats().total

    report = run_reflection_experiment(store, cases, _fake_reflector(), machine_id="m", ks=(1, 3))

    assert report.after.working_set.per_project["p"] < report.before.working_set.per_project["p"]
    assert not report.recall_regressed
    assert report.reflected.get("p", 0) >= 1
    # The live store was not mutated by the experiment: no episodic re-tagged and,
    # crucially, no distilled note (semantic or otherwise) leaked into the live store.
    assert all("reflected" not in m.tags for m in store.list(type="episodic"))
    assert store.stats().total == before_total
    store.close()


def test_experiment_skips_below_threshold_project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ANAMNESIS_REFLECT_MIN_EPISODICS", "5")
    store = MemoryStore(tmp_path / "s")
    store.write(type="episodic", title="only one", body="b", project="p")
    report = run_reflection_experiment(store, [], _fake_reflector(), machine_id="m", ks=(1,))
    assert "p" in report.skipped
    assert report.reflected == {}
    store.close()


def test_experiment_records_failed_project(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("ANAMNESIS_REFLECT_MIN_EPISODICS", "2")
    store = MemoryStore(tmp_path / "s")
    # Enough portable episodics to meet the threshold so reflection is attempted.
    for i in range(2):
        store.write(type="episodic", title=f"Session {i}", body="chatter " * 80, project="p")
    cases: list[EvalCase] = []
    before_total = store.stats().total

    def client(system: str, user: str) -> str:
        raise RuntimeError("boom")

    reflector = Reflector(client=client, model_label="fake/model")

    # One project erroring must not abort the experiment.
    report = run_reflection_experiment(store, cases, reflector, machine_id="m", ks=(1,))

    assert "p" in report.failed
    assert "p" not in report.reflected
    assert "p" not in report.skipped
    text = render_experiment(report)
    assert "failed" in text
    assert "p" in text
    # The live store is unchanged by the failed experiment.
    assert store.stats().total == before_total
    store.close()


def test_render_experiment_flags_regression():
    from anamnesis.eval import BaselineReport, RecallReport, WorkingSetReport

    before = BaselineReport(
        recall=RecallReport(1, {1: 1.0}, 1.0),
        working_set=WorkingSetReport({"p": 100}, 100.0, 100.0, 1000),
    )
    after = BaselineReport(
        recall=RecallReport(1, {1: 0.0}, 0.0),
        working_set=WorkingSetReport({"p": 50}, 50.0, 50.0, 1000),
    )
    report = ExperimentReport(before=before, after=after, reflected={"p": 1}, skipped=[], ks=(1,))
    text = render_experiment(report)
    assert "REGRESSION" in text
    assert report.recall_regressed is True
    assert report.inject_delta_pct < 0
