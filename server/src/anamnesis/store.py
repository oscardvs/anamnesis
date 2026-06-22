"""The Anamnesis memory store core.

Markdown files are the source of truth; a SQLite (WAL + FTS5) index is derived
from them and can always be rebuilt with :meth:`MemoryStore.reindex`. See the
architecture doc (docs/architecture.md, local-only) for the full design.

Layout under ``root`` (default ``~/.anamnesis``)::

    root/
      memory/                 # SOURCE OF TRUTH - markdown, one file per note
        <type>/<id>.md
      index.db                # DERIVED - SQLite (WAL, FTS5, structured tables)
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml
from ulid import ULID

MemoryType = str  # "procedural" | "semantic" | "episodic"
Scope = str  # "portable" | "machine-local"

_FM_DELIM = "---\n"


def _utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _fts_query(query: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression.

    Each word becomes a quoted phrase (terms ANDed). FTS5-special characters
    (``-``, ``:``, ``*``, ``"`` ...) are neutralized so arbitrary user or imported
    text cannot break the query parser. Returns "" if there are no word tokens.
    """
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)
    return " ".join(f'"{t}"' for t in tokens)


@dataclass
class Memory:
    """A single memory note. Mirrors the markdown front-matter (architecture §3)."""

    id: str
    type: MemoryType
    title: str
    body: str
    project: str = "global"
    machine_id: str = "unknown"
    scope: Scope = "portable"
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    prov_source: str = "human"  # human | session-end | reflection | import
    prov_model: str = ""
    prov_session: str = ""
    confidence: float = 1.0
    supersedes: str = ""


@dataclass
class StoreStats:
    """Aggregate index health, surfaced by ``memory_status`` (architecture §5.1)."""

    total: int
    by_type: dict[str, int]
    by_project: dict[str, int]
    by_scope: dict[str, int] = field(default_factory=dict)


def _serialize(mem: Memory) -> str:
    """Render a Memory as a markdown file: YAML front-matter + body."""
    meta: dict[str, object] = {
        "id": mem.id,
        "type": mem.type,
        "title": mem.title,
        "project": mem.project,
        "machine_id": mem.machine_id,
        "scope": mem.scope,
        "prov_source": mem.prov_source,
        "confidence": mem.confidence,
    }
    if mem.prov_model:
        meta["prov_model"] = mem.prov_model
    if mem.prov_session:
        meta["prov_session"] = mem.prov_session
    if mem.supersedes:
        meta["supersedes"] = mem.supersedes
    meta["created_at"] = mem.created_at
    meta["updated_at"] = mem.updated_at
    meta["tags"] = mem.tags
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
    return f"{_FM_DELIM}{front}{_FM_DELIM}{mem.body}\n"


def _deserialize(text: str) -> Memory:
    """Parse a markdown file (front-matter + body) back into a Memory."""
    if not text.startswith(_FM_DELIM):
        raise ValueError("memory file missing YAML front-matter")
    front_str, _, body = text[len(_FM_DELIM) :].partition("\n" + _FM_DELIM)
    meta = yaml.safe_load(front_str) or {}
    if body.endswith("\n"):
        body = body[:-1]  # drop the single trailing newline added on write
    return Memory(
        id=meta["id"],
        type=meta["type"],
        title=meta["title"],
        body=body,
        project=meta.get("project", "global"),
        machine_id=meta.get("machine_id", "unknown"),
        scope=meta.get("scope", "portable"),
        tags=list(meta.get("tags") or []),
        created_at=meta.get("created_at", ""),
        updated_at=meta.get("updated_at", ""),
        prov_source=meta.get("prov_source", "human"),
        prov_model=meta.get("prov_model", ""),
        prov_session=meta.get("prov_session", ""),
        confidence=float(meta.get("confidence", 1.0)),
        supersedes=meta.get("supersedes", ""),
    )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
  id           TEXT PRIMARY KEY,
  type         TEXT NOT NULL CHECK (type IN ('procedural','semantic','episodic')),
  title        TEXT NOT NULL,
  body_path    TEXT NOT NULL,
  project      TEXT NOT NULL DEFAULT 'global',
  machine_id   TEXT NOT NULL,
  scope        TEXT NOT NULL DEFAULT 'portable' CHECK (scope IN ('portable','machine-local')),
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  prov_source  TEXT NOT NULL DEFAULT 'human'
               CHECK (prov_source IN ('human','session-end','reflection','import')),
  prov_model   TEXT,
  prov_session TEXT,
  confidence   REAL NOT NULL DEFAULT 1.0,
  supersedes   TEXT
);
CREATE INDEX IF NOT EXISTS idx_mem_scope   ON memories(project, type, scope);
CREATE INDEX IF NOT EXISTS idx_mem_recency ON memories(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_mem_prov    ON memories(prov_source);

CREATE TABLE IF NOT EXISTS memory_tags (
  memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  tag       TEXT NOT NULL,
  PRIMARY KEY (memory_id, tag)
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
  id UNINDEXED, title, body, tags, tokenize='porter unicode61'
);
"""

_SCHEMA_VERSION = 1


class MemoryStore:
    """File-first memory store with a rebuildable SQLite index."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.memory_dir = self.root / "memory"
        # Machine-local notes live here, OUTSIDE the git-synced memory/ tree, so
        # they are never pushed to other machines (architecture: scope split).
        self.local_dir = self.root / "local"
        self.db_path = self.root / "index.db"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.local_dir.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the FastMCP server runs sync tools in a worker
        # threadpool, so the connection is shared across threads. SQLite's
        # serialized threadsafety + WAL + busy_timeout (below) keep that safe.
        db_existed = self.db_path.exists()
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        needs_migration = db_existed and version < _SCHEMA_VERSION
        if needs_migration:
            # The index is fully derived from markdown, so the safe upgrade is to
            # drop the derived tables, recreate them with the current schema, and
            # reindex from the markdown source of truth.
            self._db.executescript(
                "DROP TABLE IF EXISTS memories;"
                "DROP TABLE IF EXISTS memory_tags;"
                "DROP TABLE IF EXISTS memories_fts;"
            )
        self._db.executescript(_SCHEMA)
        self._db.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        self._db.commit()
        if needs_migration:
            self.reindex()

    def _dir_for_scope(self, scope: Scope) -> Path:
        """The tree a note lives in: machine-local stays out of the synced memory/."""
        return self.local_dir if scope == "machine-local" else self.memory_dir

    def write(
        self,
        *,
        type: MemoryType,
        title: str,
        body: str,
        project: str = "global",
        machine_id: str = "unknown",
        tags: list[str] | None = None,
        scope: Scope = "portable",
        prov_source: str = "human",
        prov_model: str = "",
        prov_session: str = "",
        confidence: float = 1.0,
        supersedes: str = "",
    ) -> Memory:
        """Create a memory: write the markdown file, then index it."""
        now = _utcnow()
        mem = Memory(
            id=str(ULID()),
            type=type,
            title=title,
            body=body,
            project=project,
            machine_id=machine_id,
            scope=scope,
            tags=list(tags or []),
            created_at=now,
            updated_at=now,
            prov_source=prov_source,
            prov_model=prov_model,
            prov_session=prov_session,
            confidence=confidence,
            supersedes=supersedes,
        )
        rel_path = f"{mem.type}/{mem.id}.md"
        abs_path = self._dir_for_scope(mem.scope) / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(_serialize(mem), encoding="utf-8")
        try:
            self._index(mem, rel_path)
        except Exception:
            abs_path.unlink(missing_ok=True)
            raise
        self._db.commit()
        return mem

    def put(self, mem: Memory) -> Memory:
        """Persist a fully-formed memory (explicit id) and index it; upsert by id.

        Unlike :meth:`write`, the caller supplies the id and timestamps. Used by
        the native-memory importer, which derives a stable id per source note so
        re-imports overwrite in place rather than duplicating.
        """
        rel_path = f"{mem.type}/{mem.id}.md"
        abs_path = self._dir_for_scope(mem.scope) / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(_serialize(mem), encoding="utf-8")
        try:
            self._index(mem, rel_path)
        except Exception:
            abs_path.unlink(missing_ok=True)
            raise
        self._db.commit()
        return mem

    def search(
        self,
        query: str,
        *,
        project: str | None = None,
        type: MemoryType | None = None,
        scope: Scope | None = None,
        k: int = 8,
    ) -> list[Memory]:
        """Keyword (FTS5 BM25) search, optionally scoped by project/type/scope."""
        match = _fts_query(query)
        if not match:
            return []
        sql = [
            "SELECT m.id FROM memories_fts f",
            "JOIN memories m ON m.id = f.id",
            "WHERE memories_fts MATCH ?",
        ]
        params: list[object] = [match]
        if project is not None:
            sql.append("AND m.project = ?")
            params.append(project)
        if type is not None:
            sql.append("AND m.type = ?")
            params.append(type)
        if scope is not None:
            sql.append("AND m.scope = ?")
            params.append(scope)
        sql.append("ORDER BY bm25(memories_fts), m.updated_at DESC LIMIT ?")
        params.append(k)
        rows = self._db.execute(" ".join(sql), params).fetchall()
        return [self.get(r["id"]) for r in rows]

    def list(
        self,
        *,
        project: str | None = None,
        type: MemoryType | None = None,
        scope: Scope | None = None,
    ) -> list[Memory]:
        """List memories (newest first), optionally scoped by project/type/scope."""
        sql = ["SELECT id FROM memories"]
        clauses: list[str] = []
        params: list[object] = []
        if project is not None:
            clauses.append("project = ?")
            params.append(project)
        if type is not None:
            clauses.append("type = ?")
            params.append(type)
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope)
        if clauses:
            sql.append("WHERE " + " AND ".join(clauses))
        sql.append("ORDER BY updated_at DESC, id DESC")
        rows = self._db.execute(" ".join(sql), params).fetchall()
        return [self.get(r["id"]) for r in rows]

    def stats(self) -> StoreStats:
        """Aggregate counts from the index (itself rebuildable from markdown)."""
        total = self._db.execute("SELECT COUNT(*) AS c FROM memories").fetchone()["c"]
        by_type = {
            r["type"]: r["c"]
            for r in self._db.execute("SELECT type, COUNT(*) AS c FROM memories GROUP BY type")
        }
        by_project = {
            r["project"]: r["c"]
            for r in self._db.execute(
                "SELECT project, COUNT(*) AS c FROM memories GROUP BY project"
            )
        }
        by_scope = {
            r["scope"]: r["c"]
            for r in self._db.execute("SELECT scope, COUNT(*) AS c FROM memories GROUP BY scope")
        }
        return StoreStats(total=total, by_type=by_type, by_project=by_project, by_scope=by_scope)

    def get(self, memory_id: str) -> Memory:
        """Read a memory back from its markdown file (the source of truth)."""
        row = self._db.execute(
            "SELECT body_path, scope FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            raise KeyError(memory_id)
        base = self._dir_for_scope(row["scope"])
        text = (base / row["body_path"]).read_text(encoding="utf-8")
        return _deserialize(text)

    def reindex(self) -> int:
        """Rebuild the entire SQLite index from the markdown files. Returns count."""
        self._db.execute("DELETE FROM memories")
        self._db.execute("DELETE FROM memory_tags")
        self._db.execute("DELETE FROM memories_fts")
        count = 0
        # The tree a note lives in is authoritative for its scope: memory/ is
        # portable (synced), local/ is machine-local (never synced).
        for base, scope in ((self.memory_dir, "portable"), (self.local_dir, "machine-local")):
            for path in sorted(base.rglob("*.md")):
                mem = _deserialize(path.read_text(encoding="utf-8"))
                mem.scope = scope
                self._index(mem, str(path.relative_to(base)))
                count += 1
        self._db.commit()
        return count

    def close(self) -> None:
        """Close the SQLite connection."""
        self._db.close()

    # -- internals ---------------------------------------------------------

    def _index(self, mem: Memory, rel_path: str) -> None:
        self._db.execute(
            """INSERT OR REPLACE INTO memories
               (id, type, title, body_path, project, machine_id, scope, created_at, updated_at,
                prov_source, prov_model, prov_session, confidence, supersedes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mem.id,
                mem.type,
                mem.title,
                rel_path,
                mem.project,
                mem.machine_id,
                mem.scope,
                mem.created_at,
                mem.updated_at,
                mem.prov_source,
                mem.prov_model or None,
                mem.prov_session or None,
                mem.confidence,
                mem.supersedes or None,
            ),
        )
        self._db.execute("DELETE FROM memory_tags WHERE memory_id = ?", (mem.id,))
        self._db.executemany(
            "INSERT INTO memory_tags (memory_id, tag) VALUES (?, ?)",
            [(mem.id, t) for t in mem.tags],
        )
        self._db.execute("DELETE FROM memories_fts WHERE id = ?", (mem.id,))
        self._db.execute(
            "INSERT INTO memories_fts (id, title, body, tags) VALUES (?, ?, ?, ?)",
            (mem.id, mem.title, mem.body, " ".join(mem.tags)),
        )
