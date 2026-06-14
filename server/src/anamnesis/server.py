"""The Anamnesis FastMCP server - exposes the memory store to Claude Code.

A thin layer over :class:`~anamnesis.store.MemoryStore` (architecture §5.1).
Markdown stays the source of truth; this module just maps MCP tool calls onto
the store. The store root is resolved from ``ANAMNESIS_HOME`` (default
``~/.anamnesis``); the machine-of-origin for writes from ``ANAMNESIS_MACHINE_ID``
(default the hostname).

Tools (read-only query tools carry ``readOnlyHint`` so a client can auto-approve
them; writes are flagged for confirmation):

- ``memory_search(query, project?, type?, k=8)``  read-only
- ``memory_list(project?, type?)``                read-only
- ``memory_status()``                             read-only
- ``memory_write(type, title, body, project, tags?)``  write - confirm
- ``memory_sync(force?)``                         write - stub until sync lands

The store layer never imports FastMCP; the dependency points one way (server ->
store) so the engine stays usable without the MCP extra.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from anamnesis.store import Memory, MemoryStore, MemoryType


def resolve_home() -> Path:
    """Resolve the store root from ``ANAMNESIS_HOME`` (default ``~/.anamnesis``)."""
    raw = os.environ.get("ANAMNESIS_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".anamnesis"


def resolve_machine_id() -> str:
    """Resolve this machine's id from ``ANAMNESIS_MACHINE_ID`` (default hostname)."""
    return os.environ.get("ANAMNESIS_MACHINE_ID") or socket.gethostname() or "unknown"


def _memory_dict(mem: Memory, *, include_body: bool) -> dict[str, object]:
    """Render a Memory as a JSON-friendly dict; ``include_body`` toggles the body."""
    out: dict[str, object] = {
        "id": mem.id,
        "type": mem.type,
        "title": mem.title,
        "project": mem.project,
        "machine_id": mem.machine_id,
        "scope": mem.scope,
        "tags": mem.tags,
        "created_at": mem.created_at,
        "updated_at": mem.updated_at,
    }
    if include_body:
        out["body"] = mem.body
    return out


# -- tool logic (pure; tested directly against a temp store) ------------------


def search_memories(
    store: MemoryStore,
    *,
    query: str,
    project: str | None = None,
    type: MemoryType | None = None,
    k: int = 8,
) -> list[dict[str, object]]:
    """Keyword search (FTS5 BM25); returns ranked notes with body + metadata."""
    hits = store.search(query, project=project, type=type, k=k)
    return [_memory_dict(m, include_body=True) for m in hits]


def list_memories(
    store: MemoryStore,
    *,
    project: str | None = None,
    type: MemoryType | None = None,
) -> list[dict[str, object]]:
    """List notes newest-first; returns titles + metadata (no bodies)."""
    return [_memory_dict(m, include_body=False) for m in store.list(project=project, type=type)]


def write_memory(
    store: MemoryStore,
    *,
    type: MemoryType,
    title: str,
    body: str,
    project: str = "global",
    tags: list[str] | None = None,
    machine_id: str = "unknown",
) -> dict[str, object]:
    """Create a durable note (writes markdown + indexes it); returns its metadata."""
    mem = store.write(
        type=type,
        title=title,
        body=body,
        project=project,
        machine_id=machine_id,
        tags=tags or [],
    )
    return _memory_dict(mem, include_body=True)


def status_report(store: MemoryStore) -> dict[str, object]:
    """Report index health (counts + paths) and sync state (not yet wired)."""
    s = store.stats()
    return {
        "root": str(store.root),
        "db_path": str(store.db_path),
        "total": s.total,
        "by_type": s.by_type,
        "by_project": s.by_project,
        "sync": {"configured": False, "detail": "git-over-Tailscale sync not yet implemented"},
    }


# -- FastMCP wiring ----------------------------------------------------------

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def build_server(store: MemoryStore, *, machine_id: str | None = None) -> FastMCP:
    """Build a FastMCP server whose tools are bound to ``store``."""
    mid = machine_id or resolve_machine_id()
    mcp: FastMCP = FastMCP(name="anamnesis")

    @mcp.tool(annotations=_READ_ONLY)
    def memory_search(
        query: str,
        project: str | None = None,
        type: str | None = None,
        k: int = 8,
    ) -> list[dict[str, object]]:
        """Search memory by keyword (FTS5 BM25), optionally scoped by project/type.

        Read-only. Returns up to ``k`` ranked notes, each with its body and
        metadata (id, type, project, machine of origin, tags, timestamps).
        """
        return search_memories(store, query=query, project=project, type=type, k=k)

    @mcp.tool(annotations=_READ_ONLY)
    def memory_list(
        project: str | None = None,
        type: str | None = None,
    ) -> list[dict[str, object]]:
        """List memory notes newest-first (titles + metadata, no bodies).

        Read-only. Optionally scoped by project and/or type.
        """
        return list_memories(store, project=project, type=type)

    @mcp.tool(annotations=_READ_ONLY)
    def memory_status() -> dict[str, object]:
        """Report store health: counts by type/project, store paths, sync state.

        Read-only.
        """
        return status_report(store)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def memory_write(
        type: str,
        title: str,
        body: str,
        project: str = "global",
        tags: list[str] | None = None,
    ) -> dict[str, object]:
        """Create a durable memory note: write the markdown file and index it.

        Use ``type`` = procedural (verified how-tos, decisions, fixes), semantic
        (facts, preferences, conventions), or episodic (what happened). The note
        is tagged with this machine as its origin. Returns the created note's
        metadata. This modifies the store, so it is not auto-approved.
        """
        return write_memory(
            store, type=type, title=title, body=body, project=project, tags=tags, machine_id=mid
        )

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
    def memory_sync(force: bool = False) -> dict[str, object]:
        """Sync memory across machines (git over Tailscale). Not yet implemented.

        Stub until the sync layer lands; reports its status instead of acting.
        """
        return {
            "ok": False,
            "status": "not_implemented",
            "detail": "git-over-Tailscale sync lands in the next milestone",
        }

    return mcp


def main() -> None:
    """Console entry point: serve the store over stdio for Claude Code."""
    build_server(MemoryStore(resolve_home())).run()


if __name__ == "__main__":
    main()
