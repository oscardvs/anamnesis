"""Backfill provenance on existing notes: infer prov_source from a note's tags and
rewrite its front-matter. One-time, reversible via git. Operates on the markdown
source of truth; the index is rebuilt afterwards by the caller.

Generic logic, tested with synthetic fixtures: no personal data here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from anamnesis.store import Memory, _deserialize, _serialize


@dataclass
class BackfillChange:
    """One note whose prov_source is (re)set from its tags."""

    note_id: str
    project: str
    title: str
    prov_source: str


def _infer_source(mem: Memory) -> str:
    """Infer prov_source from a note's tags: import beats session beats human."""
    if "import" in mem.tags:
        return "import"
    if "session" in mem.tags:
        return "session-end"
    return "human"


def _load_all(dirs: list[Path]) -> list[tuple[Memory, Path]]:
    out: list[tuple[Memory, Path]] = []
    for base in dirs:
        for path in sorted(base.rglob("*.md")):
            try:
                mem = _deserialize(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, KeyError):
                continue
            out.append((mem, path))
    return out


def plan_backfill(dirs: list[Path]) -> list[BackfillChange]:
    """List notes whose inferred prov_source differs from their current value."""
    changes: list[BackfillChange] = []
    for mem, _ in _load_all(dirs):
        inferred = _infer_source(mem)
        if mem.prov_source != inferred:
            changes.append(BackfillChange(mem.id, mem.project, mem.title, inferred))
    return changes


def apply_backfill(dirs: list[Path]) -> list[BackfillChange]:
    """Rewrite each changed note's front-matter with the inferred prov_source."""
    changes: list[BackfillChange] = []
    for mem, path in _load_all(dirs):
        inferred = _infer_source(mem)
        if mem.prov_source == inferred:
            continue
        mem.prov_source = inferred
        path.write_text(_serialize(mem), encoding="utf-8")
        changes.append(BackfillChange(mem.id, mem.project, mem.title, inferred))
    return changes
