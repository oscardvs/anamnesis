"""The ``anamnesis`` command-line entry point.

Subcommands the Claude Code hooks invoke (architecture section 5.2): ``serve``
(the MCP server), ``sync``, ``status``, ``inject`` (SessionStart), ``capture``
(SessionEnd / PreCompact). Kept free of FastMCP except inside ``serve`` so the
hook hot path works without the optional ``mcp`` extra.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from anamnesis.capture import ParsedSession, parse_transcript, resolve_summarizer, write_episodic
from anamnesis.config import resolve_claude_home, resolve_home, resolve_machine_id, resolve_remote
from anamnesis.dedup import apply_dedup, plan_dedup
from anamnesis.inject import render_inject, resolve_project_key, select_inject
from anamnesis.migrate import apply_migration, plan_migration
from anamnesis.native_import import ImportResult, import_native
from anamnesis.onboard import InitOptions, run_init
from anamnesis.provenance import apply_backfill, plan_backfill
from anamnesis.reflect import (
    apply_reflection,
    make_reflector,
    resolve_min_episodics,
    select_unreflected,
)
from anamnesis.store import MemoryStore
from anamnesis.sync import GitSyncBackend, SyncResult


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="anamnesis", description="Cross-machine memory for Claude Code."
    )
    sub = p.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")
    sub.add_parser("sync", help="run one git sync cycle and reindex")
    sub.add_parser("reindex", help="rebuild the SQLite index from markdown (no git sync)")
    sub.add_parser("status", help="print store and sync status")
    pi = sub.add_parser("inject", help="print top notes for the project as SessionStart context")
    pi.add_argument("--project", default=None)
    pi.add_argument("--k", type=int, default=8)
    pc = sub.add_parser("capture", help="write an episodic note from a transcript")
    pc.add_argument("--transcript", default=None)
    pc.add_argument("--project", default=None)
    pc.add_argument("--source", default="session-end")
    pc.add_argument("--no-sync", action="store_true")
    pim = sub.add_parser(
        "import", help="import Claude Code's native per-project memory into the store"
    )
    pim.add_argument("--claude-home", dest="claude_home", default=None)
    pim.add_argument("--no-sync", action="store_true")
    pmig = sub.add_parser(
        "migrate", help="re-key note projects from a JSON map (dry-run unless --apply)"
    )
    pmig.add_argument("--map", dest="map_path", required=True)
    pmig.add_argument("--apply", action="store_true")
    pmig.add_argument("--no-sync", action="store_true")
    pded = sub.add_parser(
        "dedup", help="remove notes with a byte-identical body (dry-run unless --apply)"
    )
    pded.add_argument("--apply", action="store_true")
    pded.add_argument("--no-sync", action="store_true")
    pbf = sub.add_parser(
        "backfill-provenance",
        help="infer prov_source from tags and rewrite front-matter (dry-run unless --apply)",
    )
    pbf.add_argument("--apply", action="store_true")
    pbf.add_argument("--no-sync", action="store_true")
    pref = sub.add_parser(
        "reflect",
        help="distill a project's episodic notes into durable notes (dry-run unless --apply)",
    )
    pref.add_argument("--project", default=None)
    pref.add_argument("--apply", action="store_true")
    pref.add_argument("--no-sync", action="store_true")
    pin = sub.add_parser(
        "init", help="configure Claude Code (MCP + hooks), set up the store, and first sync"
    )
    pin.add_argument("--home", default=None)
    pin.add_argument("--machine-id", dest="machine_id", default=None)
    grem = pin.add_mutually_exclusive_group()
    grem.add_argument("--remote", default=None)
    grem.add_argument("--local-only", dest="local_only", action="store_true")
    gcmd = pin.add_mutually_exclusive_group()
    gcmd.add_argument("--command", dest="override_command", default=None)
    gcmd.add_argument("--uv-project", dest="uv_project", default=None)
    pin.add_argument("--name", default="anamnesis")
    pin.add_argument("--no-mcp", dest="no_mcp", action="store_true")
    pin.add_argument("--no-hooks", dest="no_hooks", action="store_true")
    pin.add_argument("--no-sync", dest="no_sync", action="store_true")
    pin.add_argument("--yes", action="store_true")
    pin.add_argument("--print", dest="print_plan", action="store_true")
    return p


def resolve_command(argv: list[str]) -> str:
    """The subcommand to run, defaulting to ``serve`` when none is given."""
    return build_parser().parse_args(argv).command or "serve"


def read_hook_payload() -> dict[str, object]:
    """Read the hook JSON payload from stdin (empty dict if none, piped, or invalid)."""
    stdin = sys.stdin
    if stdin is None or stdin.isatty():
        return {}
    try:
        raw = stdin.read()
    except (OSError, ValueError):
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _backend(store: MemoryStore) -> GitSyncBackend:
    return GitSyncBackend(
        store.memory_dir, remote=resolve_remote(), machine_id=resolve_machine_id()
    )


def _maybe_import_native(store: MemoryStore) -> None:
    """Mirror Claude Code's native memory into the store before a sync (best-effort).

    Disabled by ``ANAMNESIS_IMPORT_NATIVE=0``. Failures never break the sync hot
    path: they are reported to stderr and the sync proceeds.
    """
    if os.environ.get("ANAMNESIS_IMPORT_NATIVE", "1") == "0":
        return
    try:
        import_native(store, claude_home=resolve_claude_home(), machine_id=resolve_machine_id())
    except Exception as exc:  # noqa: BLE001 - import must never break a sync
        print(f"import: skipped native import ({exc})", file=sys.stderr)


def _run_sync(store: MemoryStore, backend: GitSyncBackend) -> SyncResult:
    """One sync cycle: import native memory, commit/pull --rebase/push, then reindex."""
    _maybe_import_native(store)
    result = backend.sync()
    store.reindex()
    return result


def cmd_inject(args: argparse.Namespace, payload: dict[str, object]) -> int:
    """SessionStart: print top notes for the session's project to stdout."""
    store = MemoryStore(resolve_home())
    try:
        project = args.project or resolve_project_key(str(payload.get("cwd") or "."))
        text = render_inject(select_inject(store, project=project, k=args.k))
        if text:
            sys.stdout.write(text)
    finally:
        store.close()
    return 0


def cmd_capture(args: argparse.Namespace, payload: dict[str, object]) -> int:
    """SessionEnd / PreCompact: write an episodic note, then sync unless --no-sync."""
    transcript = args.transcript or payload.get("transcript_path")
    store = MemoryStore(resolve_home())
    try:
        session = parse_transcript(str(transcript)) if transcript else ParsedSession()
        cwd = session.cwd or str(payload.get("cwd") or ".")
        project = args.project or resolve_project_key(cwd)
        mem = write_episodic(
            store,
            session,
            summarizer=resolve_summarizer(),
            project=project,
            source=args.source,
            machine_id=resolve_machine_id(),
        )
        if mem is None:
            print(f"capture: skipped trivial session (project={project}, source={args.source})")
        else:
            print(
                f"capture: wrote episodic note {mem.id} (project={project}, source={args.source})"
            )
        if not args.no_sync:
            result = _run_sync(store, _backend(store))
            print(f"capture: synced (pushed={result.pushed} pulled={result.pulled})")
    finally:
        store.close()
    return 0


def _load_map(path: str) -> tuple[dict[str, str], dict[str, str]]:
    """Read the migration map JSON: ``{"projects": {...}, "notes": {...}}``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}, {}
    projects = data.get("projects") or {}
    notes = data.get("notes") or {}
    return (
        {str(k): str(v) for k, v in projects.items()},
        {str(k): str(v) for k, v in notes.items()},
    )


def cmd_migrate(args: argparse.Namespace) -> int:
    """Re-key note projects from a JSON map. Dry-run unless --apply."""
    project_map, note_overrides = _load_map(args.map_path)
    store = MemoryStore(resolve_home())
    try:
        if not args.apply:
            changes = plan_migration(store.memory_dir, project_map, note_overrides)
            for c in changes:
                print(f"migrate: {c.id} [{c.type}] {c.old_project!r} -> {c.new_project!r}")
            print(f"migrate: {len(changes)} note(s) would change (dry-run; pass --apply to write)")
            return 0
        changes = apply_migration(store.memory_dir, project_map, note_overrides)
        if args.no_sync:
            store.reindex()
            print(f"migrate: applied {len(changes)} change(s); reindexed (no sync)")
        else:
            result = _run_sync(store, _backend(store))
            print(
                f"migrate: applied {len(changes)} change(s); "
                f"synced (pushed={result.pushed} pulled={result.pulled})"
            )
    finally:
        store.close()
    return 0


def cmd_dedup(args: argparse.Namespace) -> int:
    """Collapse notes with a byte-identical body to one keeper. Dry-run unless --apply."""
    store = MemoryStore(resolve_home())
    try:
        if not args.apply:
            changes = plan_dedup(store.memory_dir)
            for c in changes:
                print(f"dedup: remove {c.removed_id} [{c.project}] dup of {c.kept_id} {c.title!r}")
            print(f"dedup: {len(changes)} duplicate(s) would be removed (dry-run; pass --apply)")
            return 0
        changes = apply_dedup(store.memory_dir)
        if args.no_sync:
            store.reindex()
            print(f"dedup: removed {len(changes)} duplicate(s); reindexed (no sync)")
        else:
            result = _run_sync(store, _backend(store))
            print(
                f"dedup: removed {len(changes)} duplicate(s); "
                f"synced (pushed={result.pushed} pulled={result.pulled})"
            )
    finally:
        store.close()
    return 0


def cmd_backfill_provenance(args: argparse.Namespace) -> int:
    """Infer prov_source from tags and rewrite front-matter. Dry-run unless --apply."""
    store = MemoryStore(resolve_home())
    try:
        dirs = [store.memory_dir, store.local_dir]
        if not args.apply:
            changes = plan_backfill(dirs)
            for c in changes:
                print(
                    f"backfill: {c.note_id} [{c.project}]"
                    f" -> prov_source={c.prov_source} {c.title!r}"
                )
            print(f"backfill: {len(changes)} note(s) would change (dry-run; pass --apply)")
            return 0
        changes = apply_backfill(dirs)
        if args.no_sync:
            store.reindex()
            print(f"backfill: rewrote {len(changes)} note(s); reindexed (no sync)")
        else:
            result = _run_sync(store, _backend(store))
            print(
                f"backfill: rewrote {len(changes)} note(s); "
                f"synced (pushed={result.pushed} pulled={result.pulled})"
            )
    finally:
        store.close()
    return 0


def cmd_reflect(args: argparse.Namespace) -> int:
    """Distill episodic notes into durable reflection notes. Dry-run unless --apply."""
    store = MemoryStore(resolve_home())
    try:
        min_ep = resolve_min_episodics()
        if args.project:
            projects = [args.project]
        else:
            projects = sorted({m.project for m in store.list(type="episodic", scope="portable")})
        reflector = None
        if args.apply:
            reflector = make_reflector()
            if reflector is None:
                print(
                    "reflect: no reflection provider configured "
                    "(set ANAMNESIS_REFLECTION_PROVIDER + model/base-url/key)"
                )
                return 0
        wrote = 0
        for project in projects:
            unreflected = select_unreflected(store, project)
            if len(unreflected) < min_ep:
                continue
            if not args.apply:
                print(
                    f"reflect: {project}: {len(unreflected)} episodic(s) would be distilled "
                    "(dry-run; pass --apply)"
                )
                continue
            assert reflector is not None
            try:
                result = apply_reflection(
                    store, project, reflector, machine_id=resolve_machine_id()
                )
            except Exception as exc:  # noqa: BLE001 - one project must not kill the run
                print(f"reflect: {project}: failed ({exc}); skipped")
                continue
            wrote += result.notes_written
            print(
                f"reflect: {project}: distilled {result.episodics} episodic(s) "
                f"-> {result.notes_written} note(s)"
            )
        if args.apply and wrote:
            if args.no_sync:
                store.reindex()
                print(f"reflect: wrote {wrote} note(s); reindexed (no sync)")
            else:
                synced = _run_sync(store, _backend(store))
                print(
                    f"reflect: wrote {wrote} note(s); "
                    f"synced (pushed={synced.pushed} pulled={synced.pulled})"
                )
    finally:
        store.close()
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """Import Claude Code's native memory, then sync unless --no-sync.

    The same import runs automatically inside every sync cycle; this is the
    explicit, one-shot entry point (and the way to seed a machine the first time).
    """
    claude_home = args.claude_home or resolve_claude_home()
    store = MemoryStore(resolve_home())
    try:
        result: ImportResult = import_native(
            store, claude_home=claude_home, machine_id=resolve_machine_id()
        )
        print(
            f"import: imported={result.imported} updated={result.updated} "
            f"skipped={result.skipped} (from {claude_home})"
        )
        if not args.no_sync:
            sync = _run_sync(store, _backend(store))
            print(f"import: synced (pushed={sync.pushed} pulled={sync.pulled})")
    finally:
        store.close()
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Configure Claude Code on this machine, then run a first sync."""
    opts = InitOptions(
        home=Path(args.home).expanduser() if args.home else None,
        machine_id=args.machine_id,
        remote=args.remote,
        local_only=args.local_only,
        override_command=args.override_command,
        override_uv_project=args.uv_project,
        name=args.name,
        no_mcp=args.no_mcp,
        no_hooks=args.no_hooks,
        no_sync=args.no_sync,
        yes=args.yes,
        print_only=args.print_plan,
    )
    return run_init(opts)


def cmd_serve() -> int:
    """Run the MCP server over stdio. FastMCP is imported lazily (serve-only)."""
    from anamnesis.server import build_server  # local import keeps the hot path MCP-free

    build_server(MemoryStore(resolve_home())).run()
    return 0


def cmd_sync() -> int:
    store = MemoryStore(resolve_home())
    try:
        result = _run_sync(store, _backend(store))
        print(
            f"sync: pushed={result.pushed} pulled={result.pulled} "
            f"conflicted={result.conflicted} head={result.head} ({result.detail})"
        )
    finally:
        store.close()
    return 0


def cmd_reindex() -> int:
    """Rebuild the derived SQLite index from the markdown source of truth.

    The dashboard writes notes as markdown directly, then calls this to refresh
    the FTS5 index without touching git (sync stays a separate, explicit step).
    """
    store = MemoryStore(resolve_home())
    try:
        count = store.reindex()
        print(f"reindex: indexed {count} note(s)")
    finally:
        store.close()
    return 0


def cmd_status() -> int:
    store = MemoryStore(resolve_home())
    try:
        stats = store.stats()
        state = _backend(store).state()
        print(f"store: {store.root}")
        print(f"notes: {stats.total}  by_type={stats.by_type}  by_scope={stats.by_scope}")
        print(
            f"sync: initialized={state.initialized} remote={state.remote} "
            f"head={state.head} dirty={state.dirty} ({state.detail})"
        )
    finally:
        store.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Console entry point: dispatch a subcommand (defaults to ``serve``)."""
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    args = build_parser().parse_args(argv)
    command = args.command or "serve"
    if command == "serve":
        return cmd_serve()
    if command == "sync":
        return cmd_sync()
    if command == "reindex":
        return cmd_reindex()
    if command == "status":
        return cmd_status()
    if command == "migrate":
        return cmd_migrate(args)
    if command == "dedup":
        return cmd_dedup(args)
    if command == "backfill-provenance":
        return cmd_backfill_provenance(args)
    if command == "reflect":
        return cmd_reflect(args)
    if command == "import":
        return cmd_import(args)
    if command == "init":
        return cmd_init(args)
    payload = read_hook_payload()
    if command == "inject":
        return cmd_inject(args, payload)
    if command == "capture":
        return cmd_capture(args, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
