"""Measurement harness: retrieval recall and working-set shrink (Phase 2 gate b).

Generic and public (the native_import.py contract): no hardcoded personal paths,
synthetic-fixture tests, touches the real store only at runtime. The eval set and
any sandbox/report live under the store root, outside the repo. See the design
doc (docs/superpowers/specs/2026-06-23-measurement-harness-design.md, local-only).
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anamnesis.store import MemoryStore


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
