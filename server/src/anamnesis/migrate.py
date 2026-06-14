"""One-time project re-key migration onto a stable cross-machine key scheme
(architecture section 10.2).

Generic and data-driven: callers pass a memory directory plus a project map and
per-note id overrides. No hardcoded paths or personal keys, so the logic is
public and tested on synthetic fixtures; it touches the real store only at
runtime, the same posture as capture.py. Markdown is the source of truth and only
the ``project:`` line changes (body, ``updated_at``, and every other field are
preserved), so ``git diff`` shows exactly one line per note and the memory repo's
history is the undo.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml

_FM_DELIM = "---\n"
_PROJECT_LINE = re.compile(r"^project:.*$", re.MULTILINE)


@dataclass
class Change:
    """A single planned or applied re-key of one note's project field."""

    id: str
    type: str
    old_project: str
    new_project: str


def rekey_front_matter(text: str, new_project: str) -> str:
    """Return ``text`` with only the front-matter ``project:`` line set anew.

    Operates inside the YAML front-matter block only, so a ``project:`` line in
    the body is never touched. The new value is written as a plain YAML scalar;
    every project key in use (for example ``github.com/oscardvs/anamnesis``,
    ``ros2_ws``, ``global``) is a valid unquoted scalar. Raises ``ValueError`` if
    the text has no front-matter or no ``project:`` line. Idempotent: if the
    project already equals ``new_project`` the returned text is identical.
    """
    if not text.startswith(_FM_DELIM):
        raise ValueError("note has no YAML front-matter")
    front_str, sep, body = text[len(_FM_DELIM) :].partition("\n" + _FM_DELIM)
    if not sep:
        raise ValueError("unterminated front-matter")
    if not _PROJECT_LINE.search(front_str):
        raise ValueError("front-matter has no project field")
    new_front = _PROJECT_LINE.sub(f"project: {new_project}", front_str, count=1)
    return _FM_DELIM + new_front + sep + body


def _iter_notes(memory_dir: Path | str) -> Iterator[tuple[Path, str, str, str, str]]:
    """Yield ``(path, text, id, type, project)`` for each well-formed note file.

    Malformed files (no front-matter, unterminated, no ``id``) are skipped so the
    migration never aborts on a stray file.
    """
    for path in sorted(Path(memory_dir).rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.startswith(_FM_DELIM):
            continue
        front_str, sep, _body = text[len(_FM_DELIM) :].partition("\n" + _FM_DELIM)
        if not sep:
            continue
        try:
            meta = yaml.safe_load(front_str)
        except yaml.YAMLError:
            continue
        if not isinstance(meta, dict):
            continue
        note_id = meta.get("id")
        if not isinstance(note_id, str):
            continue
        note_type = meta.get("type")
        project = meta.get("project")
        yield (
            path,
            text,
            note_id,
            note_type if isinstance(note_type, str) else "",
            project if isinstance(project, str) else "",
        )


def _target(
    note_id: str, project: str, project_map: dict[str, str], note_overrides: dict[str, str]
) -> str | None:
    """The new project key for a note (override wins over the project map), or None."""
    if note_id in note_overrides:
        return note_overrides[note_id]
    return project_map.get(project)


def plan_migration(
    memory_dir: Path | str,
    project_map: dict[str, str],
    note_overrides: dict[str, str],
) -> list[Change]:
    """The re-keys that would happen (read-only).

    Skips notes with no mapping or already at their target.
    """
    changes: list[Change] = []
    for _path, _text, note_id, note_type, project in _iter_notes(memory_dir):
        new = _target(note_id, project, project_map, note_overrides)
        if new is not None and new != project:
            changes.append(Change(note_id, note_type, project, new))
    return changes


def apply_migration(
    memory_dir: Path | str,
    project_map: dict[str, str],
    note_overrides: dict[str, str],
) -> list[Change]:
    """Rewrite the ``project`` field of every changed note. Idempotent (skips no-ops)."""
    applied: list[Change] = []
    for path, text, note_id, note_type, project in _iter_notes(memory_dir):
        new = _target(note_id, project, project_map, note_overrides)
        if new is None or new == project:
            continue
        try:
            path.write_text(rekey_front_matter(text, new), encoding="utf-8")
        except (OSError, ValueError):
            continue
        applied.append(Change(note_id, note_type, project, new))
    return applied
