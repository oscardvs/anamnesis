"""Import Claude Code's native per-project memory into the Anamnesis store.

Claude Code maintains its own memory as markdown under
``<claude_home>/projects/<slug>/memory/<name>.md``. Its front-matter carries a
``name``, a one-line ``description``, and ``metadata.type`` (one of
``user``/``feedback``/``project``/``reference``). Anamnesis does not own that
store; this module mirrors those notes in as portable Anamnesis notes so they
then sync across machines like any other memory.

The logic is generic: no hardcoded ``~/.claude`` paths (the caller passes the
Claude home), tested only with synthetic fixtures, touching real data solely at
runtime. That is the same contract as ``capture.py`` and keeps personal data out
of the public repo.

Idempotency: a note's id is derived deterministically from its source path, so a
re-import overwrites in place. A body-content index also skips any native note
whose body already exists in the store, so this never duplicates the earlier
one-off import (which preserved native bodies verbatim) or hand-written notes.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from ulid import ULID

from anamnesis.capture import parse_transcript
from anamnesis.inject import resolve_project_key
from anamnesis.store import Memory, MemoryStore, _deserialize

_FM_DELIM = "---\n"

# Native memory type -> Anamnesis note type. Feedback is "how to work" guidance,
# which is procedural; the rest are knowledge, which is semantic.
_TYPE_MAP = {
    "feedback": "procedural",
    "project": "semantic",
    "reference": "semantic",
    "user": "semantic",
}


@dataclass
class NativeNote:
    """A parsed Claude Code native memory note (front-matter + body)."""

    name: str
    description: str
    native_type: str
    body: str


@dataclass
class ImportResult:
    """Outcome of an import pass."""

    imported: int = 0
    updated: int = 0
    skipped: int = 0


def map_note_type(native_type: str) -> str:
    """Map a native memory type to an Anamnesis note type (default semantic)."""
    return _TYPE_MAP.get(native_type, "semantic")


def stable_id(ref: str) -> str:
    """A deterministic, ULID-shaped id for a native note's source reference.

    Same reference always yields the same id, so re-importing the same source
    file overwrites its note rather than creating a duplicate.
    """
    digest = hashlib.sha256(ref.encode("utf-8")).digest()[:16]
    return str(ULID.from_bytes(digest))


def _lenient_frontmatter(front_str: str) -> tuple[str, str, str]:
    """Salvage name/description/type from front-matter that is not valid YAML.

    Real native notes occasionally carry unquoted colons (e.g. a description that
    quotes ``Co-Authored-By: Claude``), which the YAML parser rejects. Rather than
    drop the note, pull the fields line by line.
    """
    name = description = native_type = ""
    in_metadata = False
    for line in front_str.splitlines():
        if re.match(r"^metadata:\s*$", line):
            in_metadata = True
            continue
        m = re.match(r"^(\s*)(\w+):\s*(.*)$", line)
        if not m:
            continue
        indent, key, value = m.groups()
        value = value.strip().strip("\"'")
        if key == "name" and not indent:
            name = value
        elif key == "description" and not indent:
            description = value
        elif key == "type" and in_metadata:
            native_type = value
    return name, description, native_type


def parse_native_note(text: str) -> NativeNote:
    """Parse a native memory markdown file into a :class:`NativeNote`.

    Falls back to a tolerant line parser when the front-matter is not valid YAML,
    so a single malformed note is salvaged rather than aborting the whole import.
    """
    if not text.startswith(_FM_DELIM):
        raise ValueError("native note missing YAML front-matter")
    front_str, _, body = text[len(_FM_DELIM) :].partition("\n" + _FM_DELIM)
    if body.endswith("\n"):
        body = body[:-1]  # mirror store serialization: drop the single trailing newline
    try:
        meta = yaml.safe_load(front_str)
        if not isinstance(meta, dict):
            raise ValueError("front-matter is not a mapping")
        metadata = meta.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        name = str(meta.get("name") or "").strip()
        description = str(meta.get("description") or "").strip()
        native_type = str(metadata.get("type") or "").strip()
    except (yaml.YAMLError, ValueError):
        name, description, native_type = _lenient_frontmatter(front_str)
    return NativeNote(name=name, description=description, native_type=native_type, body=body)


def _body_hash(body: str) -> str:
    return hashlib.sha256(body.strip().encode("utf-8")).hexdigest()


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds")


def _existing_body_index(store: MemoryStore) -> dict[str, str]:
    """Map each existing note's body-hash to its id, for content de-duplication."""
    index: dict[str, str] = {}
    for path in store.memory_dir.rglob("*.md"):
        try:
            mem = _deserialize(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        index[_body_hash(mem.body)] = mem.id
    return index


def _cwd_from_transcripts(slug_dir: Path) -> str | None:
    """The working directory recorded in any transcript under a project slug dir."""
    for jsonl in sorted(slug_dir.glob("*.jsonl")):
        session = parse_transcript(jsonl)
        if session.cwd:
            return session.cwd
    return None


def _decode_slug(slug: str, root: Path = Path("/")) -> Path:
    """Reconstruct the working directory a Claude project slug encodes.

    Claude maps both ``/`` and ``_`` to ``-`` in the slug, so the mapping is lossy
    (``/home/u/ros2_ws/src`` -> ``-home-u-ros2-ws-src``). We rebuild it by walking
    the filesystem, greedily preferring the longest ``_``-joined segment that names
    an existing directory; missing paths degrade to a plain ``-``-split.
    """
    tokens = [t for t in slug.split("-") if t]
    path = root
    i = 0
    while i < len(tokens):
        matched = False
        for j in range(len(tokens), i, -1):
            candidate = "_".join(tokens[i:j])
            if (path / candidate).is_dir():
                path = path / candidate
                i = j
                matched = True
                break
        if not matched:
            path = path / tokens[i]
            i += 1
    return path


def _project_for_slug(slug_dir: Path, resolve_project: Callable[[str], str]) -> str:
    """Resolve a stable project key for a native project dir.

    Prefer the canonical resolver applied to the working directory recorded in a
    transcript (so markers / git remotes apply exactly as for live sessions); when
    no transcript exists, resolve against the directory decoded from the slug.
    """
    cwd = _cwd_from_transcripts(slug_dir) or str(_decode_slug(slug_dir.name))
    return resolve_project(cwd)


def import_native(
    store: MemoryStore,
    *,
    claude_home: str | Path,
    machine_id: str,
    resolve_project: Callable[[str], str] = resolve_project_key,
) -> ImportResult:
    """Import every native memory note under ``claude_home`` into ``store``.

    Returns counts of notes created, updated in place, and skipped (unchanged or
    a duplicate of an existing body). A missing ``projects`` dir is a no-op.
    """
    projects_dir = Path(claude_home) / "projects"
    if not projects_dir.is_dir():
        return ImportResult()

    body_index = _existing_body_index(store)
    result = ImportResult()

    for slug_dir in sorted(p for p in projects_dir.iterdir() if p.is_dir()):
        mem_dir = slug_dir / "memory"
        if not mem_dir.is_dir():
            continue
        project = _project_for_slug(slug_dir, resolve_project)
        for md in sorted(mem_dir.glob("*.md")):
            if md.name == "MEMORY.md":
                continue  # the index file, not a note
            try:
                native = parse_native_note(md.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue

            note_type = map_note_type(native.native_type)
            note_id = stable_id(f"{slug_dir.name}/{md.stem}")
            title = native.description or native.name
            tags = ["import", f"kind:{native.native_type}"]
            ts = _mtime_iso(md)
            bhash = _body_hash(native.body)
            existing_path = store.memory_dir / f"{note_type}/{note_id}.md"

            if existing_path.exists():
                try:
                    current = _deserialize(existing_path.read_text(encoding="utf-8"))
                except (OSError, ValueError, KeyError):
                    current = None
                if (
                    current is not None
                    and current.body == native.body
                    and current.title == title
                    and current.project == project
                    and sorted(current.tags) == sorted(tags)
                ):
                    result.skipped += 1
                    continue
                created_at = current.created_at if current is not None else ts
                store.put(
                    Memory(
                        id=note_id,
                        type=note_type,
                        title=title,
                        body=native.body,
                        project=project,
                        machine_id=machine_id,
                        scope="portable",
                        tags=tags,
                        prov_source="import",
                        created_at=created_at,
                        updated_at=ts,
                    )
                )
                body_index[bhash] = note_id
                result.updated += 1
                continue

            if bhash in body_index:
                result.skipped += 1  # an existing note already holds this content
                continue

            store.put(
                Memory(
                    id=note_id,
                    type=note_type,
                    title=title,
                    body=native.body,
                    project=project,
                    machine_id=machine_id,
                    scope="portable",
                    tags=tags,
                    prov_source="import",
                    created_at=ts,
                    updated_at=ts,
                )
            )
            body_index[bhash] = note_id
            result.imported += 1

    return result
