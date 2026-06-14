"""Tests for the Anamnesis memory store core.

The store keeps markdown files as the source of truth and a SQLite (WAL + FTS5)
index derived from them. These tests pin the round-trip, search, and reindex
behavior the MCP server and importer will build on.
"""

from pathlib import Path

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
