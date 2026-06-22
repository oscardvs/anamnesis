"""Tests for the Anamnesis memory store core.

The store keeps markdown files as the source of truth and a SQLite (WAL + FTS5)
index derived from them. These tests pin the round-trip, search, and reindex
behavior the MCP server and importer will build on.
"""

import sqlite3
import threading
from pathlib import Path

import pytest

from anamnesis.store import MemoryStore


def test_write_then_get_roundtrips_all_fields(tmp_path):
    store = MemoryStore(root=tmp_path)

    mem = store.write(
        type="semantic",
        title="Prefer libSQL embedded replicas",
        body="Never sync the raw DB file; sync markdown via git.",
        project="anamnesis",
        machine_id="desktop",
        tags=["sync", "sqlite"],
    )

    got = store.get(mem.id)
    assert got.id == mem.id
    assert got.type == "semantic"
    assert got.title == "Prefer libSQL embedded replicas"
    assert got.body == "Never sync the raw DB file; sync markdown via git."
    assert got.project == "anamnesis"
    assert got.machine_id == "desktop"
    assert got.scope == "portable"  # default scope
    assert got.tags == ["sync", "sqlite"]


def test_search_finds_by_keyword_in_title_or_body(tmp_path):
    store = MemoryStore(root=tmp_path)
    hit = store.write(
        type="procedural",
        title="Use WAL mode for SQLite",
        body="Set busy_timeout on every connection.",
        project="anamnesis",
        machine_id="desktop",
    )
    miss = store.write(
        type="semantic",
        title="Tailscale mesh",
        body="git pull over the private network",
        project="anamnesis",
        machine_id="desktop",
    )

    ids = [m.id for m in store.search("busy_timeout")]
    assert hit.id in ids
    assert miss.id not in ids


def test_search_is_scoped_by_project(tmp_path):
    store = MemoryStore(root=tmp_path)
    alpha = store.write(
        type="semantic", title="shared term zeta", body="x", project="alpha", machine_id="d"
    )
    beta = store.write(
        type="semantic", title="shared term zeta", body="y", project="beta", machine_id="d"
    )

    ids = [m.id for m in store.search("zeta", project="alpha")]
    assert alpha.id in ids
    assert beta.id not in ids


def test_search_tolerates_fts_special_characters(tmp_path):
    store = MemoryStore(root=tmp_path)
    mem = store.write(
        type="semantic",
        title="Aspect ratios",
        body="A 16:9 state-of-the-art display.",
        project="p",
        machine_id="d",
    )

    # Queries containing FTS5-special characters (-, :) must not raise.
    assert mem.id in [m.id for m in store.search("state-of-the-art")]
    assert mem.id in [m.id for m in store.search("16:9")]
    # A query with no word characters yields no results rather than erroring.
    assert store.search("-") == []


def test_list_returns_all_memories_sorted_by_recency(tmp_path):
    store = MemoryStore(root=tmp_path)
    a = store.write(type="semantic", title="alpha note", body="x", project="p", machine_id="d")
    b = store.write(type="procedural", title="beta note", body="y", project="p", machine_id="d")

    got = store.list()
    assert {m.id for m in got} == {a.id, b.id}
    times = [m.updated_at for m in got]
    assert times == sorted(times, reverse=True)  # newest-first ordering


def test_list_is_scoped_by_project_and_type(tmp_path):
    store = MemoryStore(root=tmp_path)
    keep = store.write(type="procedural", title="keep", body="x", project="alpha", machine_id="d")
    store.write(type="procedural", title="other project", body="x", project="beta", machine_id="d")
    store.write(type="semantic", title="other type", body="x", project="alpha", machine_id="d")

    ids = [m.id for m in store.list(project="alpha", type="procedural")]
    assert ids == [keep.id]


def test_stats_counts_total_by_type_and_by_project(tmp_path):
    store = MemoryStore(root=tmp_path)
    store.write(type="procedural", title="a", body="x", project="p", machine_id="d")
    store.write(type="procedural", title="b", body="x", project="p", machine_id="d")
    store.write(type="semantic", title="c", body="x", project="q", machine_id="d")

    s = store.stats()
    assert s.total == 3
    assert s.by_type == {"procedural": 2, "semantic": 1}
    assert s.by_project == {"p": 2, "q": 1}


def test_store_is_usable_from_another_thread(tmp_path):
    # FastMCP runs sync tools in a worker threadpool, so the store's SQLite
    # connection must be usable from threads other than the one that opened it.
    store = MemoryStore(root=tmp_path)
    errors: list[Exception] = []
    written: list[str] = []
    found: list[str] = []

    def worker():
        try:
            mem = store.write(
                type="semantic", title="threaded", body="from a worker thread", project="p"
            )
            written.append(mem.id)
            found.extend(m.id for m in store.search("worker"))
        except Exception as exc:
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert not errors, errors
    assert written and written[0] in found


def test_reindex_rebuilds_index_from_markdown_only(tmp_path):
    # The index is derived: a machine that git-synced only the markdown (no
    # index.db) must be able to rebuild a working index from the files alone.
    store = MemoryStore(root=tmp_path)
    mem = store.write(
        type="procedural",
        title="rebuildable note",
        body="recovered from markdown",
        project="anamnesis",
        machine_id="desktop",
        tags=["recovery"],
    )
    store.close()

    # Simulate a fresh machine: delete the entire SQLite index, keep memory/.
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(store.db_path) + suffix)
        if p.exists():
            p.unlink()

    fresh = MemoryStore(root=tmp_path)
    assert fresh.search("rebuildable") == []  # empty index before reindex

    n = fresh.reindex()
    assert n == 1
    assert [m.id for m in fresh.search("rebuildable")] == [mem.id]
    assert fresh.get(mem.id).body == "recovered from markdown"
    assert fresh.get(mem.id).tags == ["recovery"]


def test_machine_local_note_lands_in_local_tree_not_synced_memory(tmp_path):
    # Machine-local notes must live OUTSIDE the git-synced memory/ tree so they
    # never sync to other machines.
    store = MemoryStore(root=tmp_path)
    mem = store.write(
        type="semantic",
        title="local secret",
        body="this machine only",
        project="p",
        machine_id="m",
        scope="machine-local",
    )
    assert mem.scope == "machine-local"
    assert not (store.memory_dir / f"{mem.type}/{mem.id}.md").exists()
    assert (tmp_path / "local" / f"{mem.type}/{mem.id}.md").exists()


def test_portable_note_still_lands_in_memory_tree(tmp_path):
    store = MemoryStore(root=tmp_path)
    mem = store.write(type="semantic", title="t", body="b", project="p", machine_id="m")
    assert mem.scope == "portable"
    assert (store.memory_dir / f"{mem.type}/{mem.id}.md").exists()


def test_get_reads_back_a_machine_local_note(tmp_path):
    store = MemoryStore(root=tmp_path)
    mem = store.write(
        type="procedural",
        title="t",
        body="local body",
        project="p",
        machine_id="m",
        scope="machine-local",
    )
    got = store.get(mem.id)
    assert got.body == "local body"
    assert got.scope == "machine-local"


def test_reindex_walks_both_trees_and_tags_scope_by_location(tmp_path):
    store = MemoryStore(root=tmp_path)
    store.write(type="semantic", title="port", body="b1", project="p", machine_id="m")
    store.write(
        type="semantic", title="loc", body="b2", project="p", machine_id="m", scope="machine-local"
    )
    assert store.reindex() == 2
    by_title = {m.title: m.scope for m in store.list(project="p")}
    assert by_title == {"port": "portable", "loc": "machine-local"}


def test_list_and_search_filter_by_scope_but_span_both_by_default(tmp_path):
    store = MemoryStore(root=tmp_path)
    store.write(type="semantic", title="alpha", body="findme one", project="p", machine_id="m")
    store.write(
        type="semantic",
        title="beta",
        body="findme two",
        project="p",
        machine_id="m",
        scope="machine-local",
    )
    assert len(store.list(project="p")) == 2  # spans both scopes
    local_only = store.list(project="p", scope="machine-local")
    assert [m.title for m in local_only] == ["beta"]

    assert len(store.search("findme", project="p")) == 2
    local_hits = store.search("findme", project="p", scope="machine-local")
    assert [m.title for m in local_hits] == ["beta"]


def test_stats_reports_counts_by_scope(tmp_path):
    store = MemoryStore(root=tmp_path)
    store.write(type="semantic", title="a", body="b", project="p", machine_id="m")
    store.write(
        type="semantic", title="c", body="d", project="p", machine_id="m", scope="machine-local"
    )
    assert store.stats().by_scope == {"portable": 1, "machine-local": 1}


from anamnesis.store import Memory, _deserialize, _serialize  # noqa: E402


def test_serialize_roundtrip_preserves_provenance():
    mem = Memory(
        id="x",
        type="semantic",
        title="t",
        body="b",
        prov_source="reflection",
        prov_model="deepseek/m",
        prov_session="s1",
        confidence=0.5,
        supersedes="old-id",
    )
    back = _deserialize(_serialize(mem))
    assert back.prov_source == "reflection"
    assert back.prov_model == "deepseek/m"
    assert back.prov_session == "s1"
    assert back.confidence == 0.5
    assert back.supersedes == "old-id"


def test_deserialize_defaults_missing_provenance():
    text = (
        "---\n"
        "id: a\ntype: semantic\ntitle: t\nproject: global\nmachine_id: m\n"
        "scope: portable\n"
        "created_at: '2026-01-01T00:00:00+00:00'\n"
        "updated_at: '2026-01-01T00:00:00+00:00'\n"
        "tags: []\n"
        "---\nbody\n"
    )
    mem = _deserialize(text)
    assert mem.prov_source == "human"
    assert mem.confidence == 1.0
    assert mem.prov_model == ""
    assert mem.supersedes == ""


def test_write_indexes_provenance(tmp_path):
    store = MemoryStore(root=tmp_path)
    mem = store.write(
        type="semantic", title="t", body="b", prov_source="reflection", confidence=0.3
    )
    row = store._db.execute(
        "SELECT prov_source, confidence FROM memories WHERE id = ?", (mem.id,)
    ).fetchone()
    assert row["prov_source"] == "reflection"
    assert row["confidence"] == 0.3
    assert store.get(mem.id).prov_source == "reflection"
    store.close()


def test_write_rejects_invalid_prov_source(tmp_path):
    store = MemoryStore(root=tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        store.write(type="semantic", title="t", body="b", prov_source="bogus")
    store.close()


def test_failed_write_leaves_no_orphan_markdown(tmp_path):
    store = MemoryStore(root=tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        store.write(type="semantic", title="t", body="b", prov_source="bogus")
    # no orphan left behind: reindex succeeds and finds nothing
    assert store.reindex() == 0
    assert list(store.memory_dir.rglob("*.md")) == []
    store.close()


_OLD_SCHEMA = """
CREATE TABLE memories (id TEXT PRIMARY KEY, type TEXT, title TEXT, body_path TEXT,
  project TEXT, machine_id TEXT, scope TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE memory_tags (memory_id TEXT, tag TEXT, PRIMARY KEY (memory_id, tag));
CREATE VIRTUAL TABLE memories_fts USING fts5(id UNINDEXED, title, body, tags);
"""

_OLD_NOTE = (
    "---\n"
    "id: n1\ntype: semantic\ntitle: Old note\nproject: global\nmachine_id: m\n"
    "scope: portable\n"
    "created_at: '2026-01-01T00:00:00+00:00'\n"
    "updated_at: '2026-01-01T00:00:00+00:00'\n"
    "tags: []\n"
    "---\nbody\n"
)


def test_open_migrates_old_index_db(tmp_path):
    # A store dir with a pre-B2a markdown note and an old-schema index.db at user_version 0.
    (tmp_path / "memory" / "semantic").mkdir(parents=True)
    (tmp_path / "memory" / "semantic" / "n1.md").write_text(_OLD_NOTE, encoding="utf-8")
    db = sqlite3.connect(tmp_path / "index.db")
    db.executescript(_OLD_SCHEMA)
    db.execute("PRAGMA user_version = 0")
    db.commit()
    db.close()

    store = MemoryStore(root=tmp_path)  # opening triggers the migration
    row = store._db.execute("SELECT prov_source FROM memories WHERE id = 'n1'").fetchone()
    assert row is not None and row["prov_source"] == "human"  # reindexed with defaults
    assert store._db.execute("PRAGMA user_version").fetchone()[0] == 1
    store.close()


def test_superseded_ids_returns_referenced_ids(tmp_path):
    store = MemoryStore(root=tmp_path)
    old = store.write(type="semantic", title="old", body="x")
    store.write(type="semantic", title="new", body="y", supersedes=old.id)
    assert store.superseded_ids() == {old.id}
    store.close()


def test_superseded_ids_empty_when_none(tmp_path):
    store = MemoryStore(root=tmp_path)
    store.write(type="semantic", title="a", body="x")
    assert store.superseded_ids() == set()
    store.close()


def test_search_excludes_superseded_but_list_includes(tmp_path):
    store = MemoryStore(root=tmp_path)
    old = store.write(type="semantic", title="alpha widget", body="the widget facts")
    store.write(
        type="semantic", title="alpha widget v2", body="the widget facts again", supersedes=old.id
    )
    hit_ids = {m.id for m in store.search("widget", k=8)}
    assert old.id not in hit_ids  # superseded hidden from recall
    assert old.id in {m.id for m in store.list()}  # but still browsable
    store.close()
