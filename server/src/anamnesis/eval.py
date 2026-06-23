"""Measurement harness: retrieval recall and working-set shrink (Phase 2 gate b).

Generic and public (the native_import.py contract): no hardcoded personal paths,
synthetic-fixture tests, touches the real store only at runtime. The eval set and
any sandbox/report live under the store root, outside the repo. See the design
doc (docs/superpowers/specs/2026-06-23-measurement-harness-design.md, local-only).
"""

from __future__ import annotations

import json
import math
import shutil
import statistics
import tempfile
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anamnesis.inject import render_inject, select_inject
from anamnesis.llm_summarizer import LLMClient, _strip_fences, _window
from anamnesis.redact import redact
from anamnesis.store import Memory, MemoryStore


def estimate_tokens(text: str) -> int:
    """Provider-agnostic token estimate: the ~4-chars/token heuristic.

    The harness only ever reports ratios and diffs of this same estimator, which
    are robust to the constant factor, so we deliberately avoid a real (networked,
    provider-specific) tokenizer. One isolated function, swappable if needed.
    """
    return math.ceil(len(text) / 4)


@dataclass
class EvalCase:
    """One eval case: a query and the ids of the notes that should answer it."""

    query: str
    relevant_ids: list[str]
    note_titles: list[str] = field(default_factory=list)
    approved: bool = False
    source: str = ""


def _dump_case(case: EvalCase) -> str:
    return json.dumps(
        {
            "query": case.query,
            "relevant_ids": case.relevant_ids,
            "note_titles": case.note_titles,
            "approved": case.approved,
            "source": case.source,
        }
    )


def _parse_case(data: dict[str, Any]) -> EvalCase:
    return EvalCase(
        query=str(data["query"]),
        relevant_ids=[str(i) for i in data.get("relevant_ids", [])],
        note_titles=[str(t) for t in data.get("note_titles", [])],
        approved=bool(data.get("approved", False)),
        source=str(data.get("source", "")),
    )


def load_eval_set(
    path: Path,
    *,
    store: MemoryStore | None = None,
    include_unreviewed: bool = False,
) -> tuple[list[EvalCase], list[str]]:
    """Load eval cases from a JSONL file.

    Returns ``(cases, warnings)``. Only ``approved`` cases are returned unless
    ``include_unreviewed`` is set. When a store is given, each relevant id is
    checked: a missing id yields a warning (never an exception) and ``note_titles``
    is refreshed from the store so curation sees current titles.
    """
    cases: list[EvalCase] = []
    warnings: list[str] = []
    unreviewed = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        case = _parse_case(json.loads(line))
        if not case.approved and not include_unreviewed:
            unreviewed += 1
            continue
        if store is not None:
            titles: list[str] = []
            for rid in case.relevant_ids:
                try:
                    titles.append(store.get(rid).title)
                except KeyError:
                    warnings.append(f"{path.name}: relevant id {rid} not in store")
            case.note_titles = titles
        cases.append(case)
    if unreviewed:
        warnings.append(f"{path.name}: {unreviewed} unreviewed candidate(s) skipped")
    return cases, warnings


def save_eval_set(path: Path, cases: Iterable[EvalCase]) -> None:
    """Write eval cases as JSONL (overwrites)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [_dump_case(c) for c in cases]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def append_candidates(path: Path, cases: Sequence[EvalCase]) -> int:
    """Append candidate cases whose query is not already present. Returns count added."""
    existing: set[str] = set()
    if path.exists():
        prior, _ = load_eval_set(path, include_unreviewed=True)
        existing = {c.query for c in prior}
    fresh = [c for c in cases if c.query not in existing]
    if not fresh:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for c in fresh:
            fh.write(_dump_case(c) + "\n")
    return len(fresh)


@dataclass
class RecallReport:
    """Recall@k and MRR over an eval set."""

    n_cases: int
    recall_at: dict[int, float]
    mrr: float


def recall_at_k(
    store: MemoryStore,
    cases: Sequence[EvalCase],
    ks: tuple[int, ...] = (1, 3, 5, 8),
) -> RecallReport:
    """Recall@k and MRR using ``store.search``.

    A case is a hit at k when any of its ``relevant_ids`` appears in the top-k
    search results; MRR uses the rank of the first relevant hit.
    """
    if not cases:
        return RecallReport(n_cases=0, recall_at={k: 0.0 for k in ks}, mrr=0.0)
    max_k = max(ks)
    hits = {k: 0 for k in ks}
    rr_total = 0.0
    for case in cases:
        result_ids = [m.id for m in store.search(case.query, k=max_k)]
        relevant = set(case.relevant_ids)
        rank: int | None = None
        for i, rid in enumerate(result_ids, start=1):
            if rid in relevant:
                rank = i
                break
        if rank is not None:
            rr_total += 1.0 / rank
            for k in ks:
                if rank <= k:
                    hits[k] += 1
    n = len(cases)
    return RecallReport(n_cases=n, recall_at={k: hits[k] / n for k in ks}, mrr=rr_total / n)


@dataclass
class WorkingSetReport:
    """Token size of the SessionStart inject block, per non-global project."""

    per_project: dict[str, int]
    mean_tokens: float
    median_tokens: float
    corpus_tokens: int


def _projects(store: MemoryStore) -> list[str]:
    """Non-global projects present in the store (global is injected into every block)."""
    return sorted(p for p in store.stats().by_project if p != "global")


def inject_working_set(store: MemoryStore, *, k: int = 8) -> WorkingSetReport:
    """Per-project inject-block tokens, plus mean/median and a full-corpus denominator.

    Mean per project, not a sum: ``global`` notes are injected every session, so
    summing across projects would multiply global tokens by the project count and
    overstate the working set.
    """
    per_project: dict[str, int] = {}
    for project in _projects(store):
        block = render_inject(select_inject(store, project=project, k=k))
        per_project[project] = estimate_tokens(block)
    sizes = list(per_project.values())
    corpus_tokens = sum(estimate_tokens(m.title) + estimate_tokens(m.body) for m in store.list())
    return WorkingSetReport(
        per_project=per_project,
        mean_tokens=statistics.mean(sizes) if sizes else 0.0,
        median_tokens=statistics.median(sizes) if sizes else 0.0,
        corpus_tokens=corpus_tokens,
    )


QUERYGEN_SYSTEM_PROMPT = (
    "You write one realistic search query a developer would type to find a specific "
    "memory note. You are given the note's title and body.\n\n"
    'Return ONLY a JSON object, no prose: {"query": <string>}.\n\n'
    "Write a natural-language question or search phrase that THIS note answers. Use "
    "DIFFERENT words from the note wherever you can (paraphrase, synonyms) so the query "
    "tests meaning-based recall rather than exact keyword overlap. One query only. "
    "Never include secrets, API keys, tokens, or credentials."
)

_QUERYGEN_MAX_CHARS = 40_000


def _parse_query(text: str) -> str:
    """Parse the model's ``{"query": ...}`` object. Raises ValueError on a bad shape."""
    data = json.loads(_strip_fences(text))
    if not isinstance(data, dict):
        raise ValueError("query-gen output is not a JSON object")
    query = str(data.get("query", "")).strip()
    if not query:
        raise ValueError("query-gen output missing 'query'")
    return query


def _sample_notes(store: MemoryStore, types: Sequence[str], n: int) -> list[Memory]:
    """Deterministic round-robin sample across projects, for coverage (no RNG)."""
    buckets: dict[str, list[Memory]] = {}
    for t in types:
        for m in store.list(type=t):
            buckets.setdefault(m.project, []).append(m)
    for ms in buckets.values():
        ms.sort(key=lambda m: m.id)
    projects = sorted(buckets)
    ordered: list[Memory] = []
    i = 0
    while any(buckets[p] for p in projects):
        bucket = buckets[projects[i % len(projects)]]
        if bucket:
            ordered.append(bucket.pop(0))
        i += 1
    return ordered[:n]


def build_eval_candidates(
    store: MemoryStore,
    client: LLMClient,
    model_label: str,
    *,
    types: Sequence[str] = ("semantic", "procedural"),
    n: int = 30,
    max_chars: int = _QUERYGEN_MAX_CHARS,
) -> list[EvalCase]:
    """Generate candidate eval cases via the LLM: one paraphrase query per sampled note.

    Each note is redacted before it reaches the client. A failed or unparseable
    response raises (no fallback, never fabricate a case).
    """
    cases: list[EvalCase] = []
    for note in _sample_notes(store, types, n):
        content = _window(redact(f"# {note.title}\n{note.body}"), max_chars)
        query = _parse_query(client(QUERYGEN_SYSTEM_PROMPT, content))
        cases.append(
            EvalCase(
                query=query,
                relevant_ids=[note.id],
                note_titles=[note.title],
                approved=False,
                source=f"llm:{model_label}",
            )
        )
    return cases


@contextmanager
def sandbox_store(store: MemoryStore) -> Iterator[MemoryStore]:
    """Yield a throwaway, reindexed copy of the store's markdown for safe experiments.

    Copies the ``memory/`` and ``local/`` trees into a temp dir and builds a fresh
    MemoryStore over the copy. The original store is never touched; the temp dir is
    removed on exit.
    """
    tmp = Path(tempfile.mkdtemp(prefix="anamnesis-eval-"))
    sandbox: MemoryStore | None = None
    try:
        for sub in ("memory", "local"):
            src = store.root / sub
            if src.exists():
                shutil.copytree(src, tmp / sub)
        sandbox = MemoryStore(tmp)
        sandbox.reindex()
        yield sandbox
    finally:
        if sandbox is not None:
            sandbox.close()
        shutil.rmtree(tmp, ignore_errors=True)


@dataclass
class BaselineReport:
    """Recall + working-set measurement of one store state."""

    recall: RecallReport
    working_set: WorkingSetReport


def run_baseline(
    store: MemoryStore,
    cases: Sequence[EvalCase],
    ks: tuple[int, ...] = (1, 3, 5, 8),
) -> BaselineReport:
    """Measure recall@k and inject working-set size on the store as-is."""
    return BaselineReport(
        recall=recall_at_k(store, cases, ks),
        working_set=inject_working_set(store),
    )


def render_baseline(report: BaselineReport) -> str:
    """A readable text report."""
    r, w = report.recall, report.working_set
    lines = [f"recall: {r.n_cases} case(s)"]
    for k in sorted(r.recall_at):
        lines.append(f"  recall@{k}: {r.recall_at[k]:.3f}")
    lines.append(f"  mrr: {r.mrr:.3f}")
    pct = (100.0 * w.mean_tokens / w.corpus_tokens) if w.corpus_tokens else 0.0
    lines.append(
        f"working set: mean={w.mean_tokens:.0f} median={w.median_tokens:.0f} tok/project "
        f"over {len(w.per_project)} project(s); corpus={w.corpus_tokens} tok "
        f"(a session injects ~{pct:.1f}% of the corpus)"
    )
    return "\n".join(lines)


def baseline_to_dict(report: BaselineReport) -> dict[str, object]:
    """A JSON-serializable view (string keys; for --json output and tracking)."""
    r, w = report.recall, report.working_set
    return {
        "recall": {
            "n_cases": r.n_cases,
            "recall_at": {str(k): v for k, v in r.recall_at.items()},
            "mrr": r.mrr,
        },
        "working_set": {
            "per_project": w.per_project,
            "mean_tokens": w.mean_tokens,
            "median_tokens": w.median_tokens,
            "corpus_tokens": w.corpus_tokens,
        },
    }
