"""Collapse duplicate notes: those whose normalized body is byte-identical.

Imports and multi-machine captures can produce identical notes (empty session
summaries, the same fact captured on several machines). This groups notes by a
content hash of the body (project is deliberately excluded, so cross-project and
cross-machine duplicates collapse) and keeps a single copy per group, preferring
the most general / oldest one. It operates on the synced ``memory/`` tree only;
machine-local notes are left alone. Reversible via the memory repo's git history.

Generic logic, tested with synthetic fixtures: no personal data here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from anamnesis.store import Memory, _deserialize


@dataclass
class DedupChange:
    """One note slated for removal because an identical-body keeper exists."""

    kept_id: str
    removed_id: str
    project: str
    title: str


def _body_hash(body: str) -> str:
    return hashlib.sha256(body.strip().encode("utf-8")).hexdigest()


def _keeper_key(mem: Memory) -> tuple[bool, str, str]:
    """Sort key for picking a keeper: prefer global, then earliest, then lowest id."""
    return (mem.project != "global", mem.created_at, mem.id)


def _load_all(memory_dir: Path) -> list[tuple[Memory, Path]]:
    out: list[tuple[Memory, Path]] = []
    for path in sorted(memory_dir.rglob("*.md")):
        try:
            mem = _deserialize(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        out.append((mem, path))
    return out


def plan_dedup(memory_dir: Path) -> list[DedupChange]:
    """List the removals that would collapse each identical-body group to one keeper."""
    groups: dict[str, list[Memory]] = {}
    for mem, _ in _load_all(memory_dir):
        groups.setdefault(_body_hash(mem.body), []).append(mem)
    changes: list[DedupChange] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=_keeper_key)
        keeper = members[0]
        for mem in members[1:]:
            changes.append(
                DedupChange(
                    kept_id=keeper.id,
                    removed_id=mem.id,
                    project=mem.project,
                    title=mem.title,
                )
            )
    return changes


def apply_dedup(memory_dir: Path) -> list[DedupChange]:
    """Delete the duplicate markdown files (keeping one per group). Returns the removals."""
    paths_by_id = {mem.id: path for mem, path in _load_all(memory_dir)}
    changes = plan_dedup(memory_dir)
    for change in changes:
        path = paths_by_id.get(change.removed_id)
        if path is not None:
            path.unlink(missing_ok=True)
    return changes
