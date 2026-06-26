"""Tests for the Anamnesis FastMCP server (architecture §5.1).

The MCP server is a thin layer over :class:`MemoryStore`. We test the tool
logic functions directly against a temp-dir store (fast, no transport), then
drive the registered tools through an in-memory FastMCP ``Client`` to prove the
wiring, schemas, and read-only annotations Claude Code actually sees.
"""

import asyncio
import subprocess
from pathlib import Path

from fastmcp import Client

from anamnesis.server import (
    build_server,
    list_memories,
    resolve_home,
    resolve_machine_id,
    search_memories,
    status_report,
    sync_memory,
    write_memory,
)
from anamnesis.store import MemoryStore
from anamnesis.sync import GitSyncBackend

# -- store root / machine identity resolution --------------------------------


def test_resolve_home_uses_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path / "store"))
    assert resolve_home() == tmp_path / "store"


def test_resolve_home_expands_user(monkeypatch):
    monkeypatch.setenv("ANAMNESIS_HOME", "~/somewhere")
    assert resolve_home() == Path.home() / "somewhere"


def test_resolve_home_defaults_to_dot_anamnesis(monkeypatch):
    monkeypatch.delenv("ANAMNESIS_HOME", raising=False)
    assert resolve_home() == Path.home() / ".anamnesis"


def test_resolve_machine_id_uses_env_override(monkeypatch):
    monkeypatch.setenv("ANAMNESIS_MACHINE_ID", "desktop-amsterdam")
    assert resolve_machine_id() == "desktop-amsterdam"


def test_resolve_machine_id_falls_back_to_nonempty(monkeypatch):
    monkeypatch.delenv("ANAMNESIS_MACHINE_ID", raising=False)
    assert resolve_machine_id()  # hostname (or "unknown") - never empty


# -- tool logic functions ----------------------------------------------------


def test_write_memory_persists_and_returns_metadata(tmp_path):
    store = MemoryStore(root=tmp_path)
    out = write_memory(
        store,
        type="semantic",
        title="t",
        body="hello world body",
        project="proj",
        tags=["a"],
        machine_id="m1",
    )
    assert out["id"]
    assert out["type"] == "semantic"
    assert out["title"] == "t"
    assert out["body"] == "hello world body"
    assert out["project"] == "proj"
    assert out["machine_id"] == "m1"
    assert out["tags"] == ["a"]
    # persisted -> searchable
    assert out["id"] in [m["id"] for m in search_memories(store, query="hello")]


def test_search_memories_returns_body_and_metadata(tmp_path):
    store = MemoryStore(root=tmp_path)
    write_memory(store, type="procedural", title="WAL mode", body="set busy_timeout", project="p")
    hits = search_memories(store, query="busy_timeout")
    assert len(hits) == 1
    assert hits[0]["title"] == "WAL mode"
    assert hits[0]["body"] == "set busy_timeout"


def test_search_memories_is_scoped_by_project(tmp_path):
    store = MemoryStore(root=tmp_path)
    write_memory(store, type="semantic", title="zeta", body="x", project="alpha")
    write_memory(store, type="semantic", title="zeta", body="y", project="beta")
    hits = search_memories(store, query="zeta", project="alpha")
    assert [h["project"] for h in hits] == ["alpha"]


def test_list_memories_returns_metadata_without_body(tmp_path):
    store = MemoryStore(root=tmp_path)
    write_memory(store, type="semantic", title="only title", body="secret body", project="p")
    items = list_memories(store)
    assert len(items) == 1
    assert items[0]["title"] == "only title"
    assert "body" not in items[0]  # list returns titles/metadata, not bodies


def test_status_report_reports_index_health_and_sync_state(tmp_path):
    store = MemoryStore(root=tmp_path)
    backend = GitSyncBackend(store.memory_dir, remote=None, machine_id="t")
    write_memory(store, type="semantic", title="a", body="x", project="p")
    write_memory(store, type="procedural", title="b", body="y", project="p")
    rep = status_report(store, backend)
    assert rep["total"] == 2
    assert rep["by_type"] == {"semantic": 1, "procedural": 1}
    assert rep["root"] == str(store.root)
    assert rep["db_path"] == str(store.db_path)
    assert rep["sync"]["initialized"] is False  # no sync run yet
    assert rep["sync"]["remote"] is None


# -- FastMCP wiring (in-memory client, no transport) -------------------------


def _list_tools(server):
    async def run():
        async with Client(server) as client:
            return await client.list_tools()

    return asyncio.run(run())


def test_build_server_registers_the_five_tools(tmp_path):
    server = build_server(MemoryStore(root=tmp_path))
    names = {t.name for t in _list_tools(server)}
    assert names == {"memory_search", "memory_list", "memory_status", "memory_write", "memory_sync"}


def test_read_only_query_tools_are_annotated_read_only(tmp_path):
    server = build_server(MemoryStore(root=tmp_path))
    by_name = {t.name: t for t in _list_tools(server)}
    for name in ("memory_search", "memory_list", "memory_status"):
        assert by_name[name].annotations.readOnlyHint is True
    assert by_name["memory_write"].annotations.readOnlyHint is False
    assert by_name["memory_sync"].annotations.readOnlyHint is False


def test_end_to_end_write_then_search_via_client(tmp_path):
    server = build_server(MemoryStore(root=tmp_path), machine_id="m-test")

    async def run():
        async with Client(server) as client:
            written = await client.call_tool(
                "memory_write",
                {
                    "type": "procedural",
                    "title": "Amsterdam scenario",
                    "body": "memory syncs across machines",
                    "project": "anamnesis",
                },
            )
            found = await client.call_tool("memory_search", {"query": "Amsterdam"})
            return written.data, found.data

    written, found = asyncio.run(run())
    assert written["machine_id"] == "m-test"
    assert any(hit["id"] == written["id"] for hit in found)


def test_sync_memory_reindexes_so_pulled_notes_are_searchable(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True
    )

    store_a = MemoryStore(root=tmp_path / "A")
    backend_a = GitSyncBackend(store_a.memory_dir, remote=str(remote), machine_id="desktop")
    write_memory(
        store_a,
        type="procedural",
        title="Amsterdam scenario",
        body="syncs across machines",
        project="anamnesis",
    )
    sync_memory(store_a, backend_a)  # push

    store_b = MemoryStore(root=tmp_path / "B")
    backend_b = GitSyncBackend(store_b.memory_dir, remote=str(remote), machine_id="laptop")
    sync_memory(store_b, backend_b)  # pull AND reindex

    # No manual reindex here: the advance-threshold requires the index rebuilt on sync.
    hits = search_memories(store_b, query="Amsterdam")
    assert [h["title"] for h in hits] == ["Amsterdam scenario"]


def test_memory_sync_without_remote_commits_locally(tmp_path, monkeypatch):
    monkeypatch.delenv("ANAMNESIS_GIT_REMOTE", raising=False)
    # Isolate the store root so resolve_remote() reads this temp store's config
    # (none here), not the developer's real ~/.anamnesis/config.json.
    monkeypatch.setenv("ANAMNESIS_HOME", str(tmp_path))
    store = MemoryStore(root=tmp_path)
    write_memory(store, type="semantic", title="note", body="x", project="p")
    server = build_server(store)

    async def run():
        async with Client(server) as client:
            return (await client.call_tool("memory_sync", {})).data

    out = asyncio.run(run())
    assert out["pushed"] is False
    assert out["conflicted"] is False
    assert "remote" in out["detail"]  # explains there is no remote configured


def test_write_memory_accepts_machine_local_scope(tmp_path):
    store = MemoryStore(root=tmp_path)
    out = write_memory(
        store,
        type="semantic",
        title="local only",
        body="stays here",
        project="p",
        machine_id="m",
        scope="machine-local",
    )
    assert out["scope"] == "machine-local"
    # written to the local/ tree, NOT the git-synced memory/ tree
    assert list((tmp_path / "local").rglob("*.md"))
    assert not list((tmp_path / "memory").rglob("*.md"))


def test_search_and_list_memories_filter_by_scope(tmp_path):
    store = MemoryStore(root=tmp_path)
    write_memory(store, type="semantic", title="alpha", body="findme", project="p", machine_id="m")
    write_memory(
        store,
        type="semantic",
        title="beta",
        body="findme",
        project="p",
        machine_id="m",
        scope="machine-local",
    )
    assert len(list_memories(store, project="p")) == 2
    local_list = list_memories(store, project="p", scope="machine-local")
    assert [m["title"] for m in local_list] == ["beta"]

    assert len(search_memories(store, query="findme", project="p")) == 2
    local_hits = search_memories(store, query="findme", project="p", scope="machine-local")
    assert [m["title"] for m in local_hits] == ["beta"]


def test_status_report_includes_by_scope(tmp_path):
    store = MemoryStore(root=tmp_path)
    write_memory(store, type="semantic", title="a", body="b", project="p", machine_id="m")
    write_memory(
        store,
        type="semantic",
        title="c",
        body="d",
        project="p",
        machine_id="m",
        scope="machine-local",
    )
    backend = GitSyncBackend(store.memory_dir, remote=None, machine_id="m")
    report = status_report(store, backend)
    assert report["by_scope"] == {"portable": 1, "machine-local": 1}


def test_memory_dict_includes_tenant(tmp_path):
    store = MemoryStore(tmp_path)
    mem = store.write(type="semantic", title="t", body="b", user_id="alice", workspace_id="team-a")
    out = search_memories(store, query="t")
    assert out[0]["user_id"] == "alice"
    assert out[0]["workspace_id"] == "team-a"
    assert mem.user_id == "alice"  # sanity


def test_write_memory_defaults_self_personal(tmp_path):
    store = MemoryStore(tmp_path)
    out = write_memory(store, type="semantic", title="t", body="b")
    assert out["user_id"] == "self"
    assert out["workspace_id"] == "personal"


def test_list_memories_filters_by_workspace(tmp_path):
    store = MemoryStore(tmp_path)
    store.write(type="semantic", title="a", body="b", workspace_id="team-a")
    store.write(type="semantic", title="c", body="d", workspace_id="team-b")
    out = list_memories(store, workspace_id="team-a")
    assert [m["workspace_id"] for m in out] == ["team-a"]
