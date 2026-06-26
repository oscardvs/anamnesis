"""The Anamnesis FastMCP server - exposes the memory store to Claude Code.

A thin layer over :class:`~anamnesis.store.MemoryStore` (architecture §5.1).
Markdown stays the source of truth; this module just maps MCP tool calls onto
the store. The store root is resolved from ``ANAMNESIS_HOME`` (default
``~/.anamnesis``); the machine-of-origin for writes from ``ANAMNESIS_MACHINE_ID``
(default the hostname).

Tools (read-only query tools carry ``readOnlyHint`` so a client can auto-approve
them; writes are flagged for confirmation):

- ``memory_search(query, project?, type?, scope?, user_id?, workspace_id?, k=8)``  read-only
- ``memory_list(project?, type?, scope?, user_id?, workspace_id?)``                read-only
- ``memory_status()``                                     read-only
- ``memory_write(type, title, body, project, tags?, scope?, user_id?, workspace_id?)``
  write - confirm
- ``memory_sync(force?)``                         write - git pull --rebase && push

The store layer never imports FastMCP; the dependency points one way (server ->
store) so the engine stays usable without the MCP extra.
"""

from __future__ import annotations

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from anamnesis.config import resolve_home, resolve_machine_id, resolve_remote
from anamnesis.store import Memory, MemoryStore, MemoryType
from anamnesis.sync import GitSyncBackend, SyncBackend


def _memory_dict(mem: Memory, *, include_body: bool) -> dict[str, object]:
    """Render a Memory as a JSON-friendly dict; ``include_body`` toggles the body."""
    out: dict[str, object] = {
        "id": mem.id,
        "type": mem.type,
        "title": mem.title,
        "project": mem.project,
        "machine_id": mem.machine_id,
        "scope": mem.scope,
        "user_id": mem.user_id,
        "workspace_id": mem.workspace_id,
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
    scope: str | None = None,
    user_id: str | None = None,
    workspace_id: str | None = None,
    k: int = 8,
) -> list[dict[str, object]]:
    """Keyword search (FTS5 BM25); returns ranked notes with body + metadata."""
    hits = store.search(
        query,
        project=project,
        type=type,
        scope=scope,
        user_id=user_id,
        workspace_id=workspace_id,
        k=k,
    )
    return [_memory_dict(m, include_body=True) for m in hits]


def list_memories(
    store: MemoryStore,
    *,
    project: str | None = None,
    type: MemoryType | None = None,
    scope: str | None = None,
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> list[dict[str, object]]:
    """List notes newest-first; returns titles + metadata (no bodies)."""
    return [
        _memory_dict(m, include_body=False)
        for m in store.list(
            project=project,
            type=type,
            scope=scope,
            user_id=user_id,
            workspace_id=workspace_id,
        )
    ]


def write_memory(
    store: MemoryStore,
    *,
    type: MemoryType,
    title: str,
    body: str,
    project: str = "global",
    tags: list[str] | None = None,
    machine_id: str = "unknown",
    scope: str = "portable",
    user_id: str = "self",
    workspace_id: str = "personal",
) -> dict[str, object]:
    """Create a durable note (writes markdown + indexes it); returns its metadata."""
    mem = store.write(
        type=type,
        title=title,
        body=body,
        project=project,
        machine_id=machine_id,
        tags=tags or [],
        scope=scope,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    return _memory_dict(mem, include_body=True)


def status_report(store: MemoryStore, backend: SyncBackend) -> dict[str, object]:
    """Report index health (counts + paths) and git sync state."""
    s = store.stats()
    st = backend.state()
    return {
        "root": str(store.root),
        "db_path": str(store.db_path),
        "total": s.total,
        "by_type": s.by_type,
        "by_project": s.by_project,
        "by_scope": s.by_scope,
        "by_workspace": s.by_workspace,
        "sync": {
            "initialized": st.initialized,
            "remote": st.remote,
            "head": st.head,
            "dirty": st.dirty,
            "detail": st.detail,
        },
    }


def sync_memory(store: MemoryStore, backend: SyncBackend) -> dict[str, object]:
    """Run one git sync cycle (commit, pull --rebase, push), then rebuild the index.

    Pulling brings in markdown from other machines; the SQLite index is derived,
    so it is rebuilt afterwards to keep search in step with the synced files.
    """
    r = backend.sync()
    indexed = store.reindex()
    return {
        "pushed": r.pushed,
        "pulled": r.pulled,
        "conflicted": r.conflicted,
        "head": r.head,
        "indexed": indexed,
        "detail": r.detail,
    }


# -- FastMCP wiring ----------------------------------------------------------

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


def build_server(store: MemoryStore, *, machine_id: str | None = None) -> FastMCP:
    """Build a FastMCP server whose tools are bound to ``store``."""
    mid = machine_id or resolve_machine_id()
    backend: SyncBackend = GitSyncBackend(store.memory_dir, remote=resolve_remote(), machine_id=mid)
    mcp: FastMCP = FastMCP(name="anamnesis")

    @mcp.tool(annotations=_READ_ONLY)
    def memory_search(
        query: str,
        project: str | None = None,
        type: str | None = None,
        scope: str | None = None,
        user_id: str | None = None,
        workspace_id: str | None = None,
        k: int = 8,
    ) -> list[dict[str, object]]:
        """Search memory by keyword (FTS5 BM25), optionally scoped by project/type/scope, and by
        user_id/workspace_id (default self/personal; set by the hosted relay, not local installs).

        Read-only. Returns up to ``k`` ranked notes, each with its body and metadata
        (id, type, project, machine of origin, scope, user_id, workspace_id, tags, timestamps).
        ``scope`` filters to "portable" (synced) or "machine-local" (this machine only).
        """
        return search_memories(
            store,
            query=query,
            project=project,
            type=type,
            scope=scope,
            user_id=user_id,
            workspace_id=workspace_id,
            k=k,
        )

    @mcp.tool(annotations=_READ_ONLY)
    def memory_list(
        project: str | None = None,
        type: str | None = None,
        scope: str | None = None,
        user_id: str | None = None,
        workspace_id: str | None = None,
    ) -> list[dict[str, object]]:
        """List memory notes newest-first (titles + metadata, no bodies).

        Read-only. Optionally scoped by project, type, and/or scope ("portable" vs "machine-local"),
        and by user_id/workspace_id (default self/personal; set by the hosted relay, not local
        installs).
        """
        return list_memories(
            store,
            project=project,
            type=type,
            scope=scope,
            user_id=user_id,
            workspace_id=workspace_id,
        )

    @mcp.tool(annotations=_READ_ONLY)
    def memory_status() -> dict[str, object]:
        """Report store health: counts by type/project, store paths, sync state.

        Read-only.
        """
        return status_report(store, backend)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def memory_write(
        type: str,
        title: str,
        body: str,
        project: str = "global",
        tags: list[str] | None = None,
        scope: str = "portable",
        user_id: str = "self",
        workspace_id: str = "personal",
    ) -> dict[str, object]:
        """Create a durable memory note: write the markdown file and index it.

        Use ``type`` = procedural (verified how-tos, decisions, fixes), semantic
        (facts, preferences, conventions), or episodic (what happened). ``scope`` =
        "portable" (default; syncs to your other machines) or "machine-local"
        (stays on this machine only, never synced). ``user_id``/``workspace_id`` default to
        "self"/"personal" and are set by the hosted relay, not local installs. The note is tagged
        with this machine as its origin. Returns the created note's metadata. This modifies the
        store, so it is not auto-approved.
        """
        return write_memory(
            store,
            type=type,
            title=title,
            body=body,
            project=project,
            tags=tags,
            machine_id=mid,
            scope=scope,
            user_id=user_id,
            workspace_id=workspace_id,
        )

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
    def memory_sync(force: bool = False) -> dict[str, object]:
        """Sync memory across machines: commit local notes, pull --rebase, push.

        Uses git over the remote in ANAMNESIS_GIT_REMOTE (a bare repo on your
        Tailscale mesh); with no remote set it just commits locally. On a
        conflicting edit it surfaces the conflict and keeps local edits rather
        than dropping either side. The ``force`` flag is reserved for future use.
        """
        return sync_memory(store, backend)

    return mcp


def main() -> None:
    """Console entry point: serve the store over stdio for Claude Code."""
    build_server(MemoryStore(resolve_home())).run()


if __name__ == "__main__":
    main()
