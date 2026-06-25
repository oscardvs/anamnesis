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
from typing import Any

from anamnesis import config
from anamnesis.capture import ParsedSession, parse_transcript, resolve_summarizer, write_episodic
from anamnesis.config import resolve_claude_home, resolve_home, resolve_machine_id, resolve_remote
from anamnesis.dedup import apply_dedup, plan_dedup
from anamnesis.eval import (
    append_candidates,
    baseline_to_dict,
    build_eval_candidates,
    load_eval_set,
    render_baseline,
    render_experiment,
    render_merge_experiment,
    resolve_merge_gate_k,
    run_baseline,
    run_merge_experiment,
    run_reflection_experiment,
    select_safe_groups,
)
from anamnesis.inject import render_inject, resolve_project_key, select_inject
from anamnesis.llm_summarizer import ping_reflection
from anamnesis.merge import (
    apply_groups,
    apply_merge,
    make_merger,
    resolve_min_durable,
    select_mergeable,
)
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
    pmrg = sub.add_parser(
        "merge",
        help="consolidate redundant durable notes by setting supersedes (dry-run unless --apply)",
    )
    pmrg.add_argument("--project", default=None)
    pmrg.add_argument("--apply", action="store_true")
    pmrg.add_argument("--no-sync", action="store_true")
    pmrg.add_argument("--no-gate", action="store_true")
    pmrg.add_argument("--eval-set", dest="eval_set", default=None)
    pev = sub.add_parser(
        "eval", help="measure recall + working-set shrink (build | run | experiment)"
    )
    evsub = pev.add_subparsers(dest="eval_command")
    evb = evsub.add_parser("build", help="generate candidate eval cases via the LLM (then curate)")
    evb.add_argument("--eval-set", dest="eval_set", default=None)
    evb.add_argument("--types", default="semantic,procedural")
    evb.add_argument("--n", type=int, default=30)
    evr = evsub.add_parser("run", help="report recall@k + inject token size on the current store")
    evr.add_argument("--eval-set", dest="eval_set", default=None)
    evr.add_argument("--include-unreviewed", dest="include_unreviewed", action="store_true")
    evr.add_argument("--json", dest="as_json", action="store_true")
    eve = evsub.add_parser(
        "experiment", help="before/after reflect on a sandbox copy (LLM-gated; live store safe)"
    )
    eve.add_argument("--eval-set", dest="eval_set", default=None)
    eve.add_argument("--include-unreviewed", dest="include_unreviewed", action="store_true")
    eve.add_argument("--merge", dest="as_merge", action="store_true")
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
    pcfg = sub.add_parser("config", help="view or edit machine-local settings (config.json)")
    cfgsub = pcfg.add_subparsers(dest="config_command")
    clist = cfgsub.add_parser("list", help="print all settings (api key masked)")
    clist.add_argument("--json", dest="as_json", action="store_true")
    cget = cfgsub.add_parser("get", help="print one setting's raw value")
    cget.add_argument("key")
    cset = cfgsub.add_parser("set", help="set settings: key value [key value ...]")
    cset.add_argument("pairs", nargs="+")
    cunset = cfgsub.add_parser("unset", help="remove a setting")
    cunset.add_argument("key")
    cfgsub.add_parser("test", help="verify the reflection provider with a minimal request")
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


def cmd_merge(args: argparse.Namespace) -> int:
    """Consolidate a project's redundant durable notes. Dry-run unless --apply.

    Both dry-run and --apply need a provider: the dry-run prints the LLM's proposed
    groups (the human checkpoint). With no provider configured, nothing is written.
    """
    store = MemoryStore(resolve_home())
    try:
        merger = make_merger()
        if merger is None:
            print(
                "merge: no reflection provider configured "
                "(set ANAMNESIS_REFLECTION_PROVIDER + model/base-url/key)"
            )
            return 0
        min_durable = resolve_min_durable()
        if args.project:
            projects = [args.project]
        else:
            projects = sorted({m.project for m in store.list(scope="portable")})
        # Recall-gated apply needs the eval set up front.
        cases = None
        if args.apply and not args.no_gate:
            eval_path = _eval_set_path(args)
            if not eval_path.exists():
                print(
                    f"merge --apply is recall-gated; no eval set at {eval_path}. "
                    "Run `anamnesis eval build` to create one, or pass --no-gate to "
                    "apply without the gate."
                )
                return 1
            cases, warnings = load_eval_set(eval_path, store=store)
            for w in warnings:
                print(f"merge: warning: {w}")
            if not cases:
                print(f"merge --apply is recall-gated; no approved eval cases in {eval_path}.")
                return 1

        gate_k = resolve_merge_gate_k()
        superseded = 0
        for project in projects:
            notes = select_mergeable(store, project)
            if len(notes) < min_durable:
                continue
            if not args.apply:
                try:
                    groups = merger.propose(notes)
                except Exception as exc:  # noqa: BLE001 - one project must not kill the run
                    print(f"merge: {project}: failed ({exc}); skipped")
                    continue
                for g in groups:
                    if g.action == "keep":
                        print(
                            f"merge: {project}: keep {g.keeper_id} supersedes "
                            f"{len(g.superseded_ids)} note(s) (dry-run; pass --apply)"
                        )
                    else:
                        print(
                            f"merge: {project}: synthesize {g.title!r} from "
                            f"{len(g.superseded_ids)} note(s) (dry-run; pass --apply)"
                        )
                if not groups:
                    print(f"merge: {project}: no redundant groups found (dry-run)")
                continue
            if args.no_gate:
                try:
                    result = apply_merge(store, project, merger, machine_id=resolve_machine_id())
                except Exception as exc:  # noqa: BLE001 - one project must not kill the run
                    print(f"merge: {project}: failed ({exc}); skipped")
                    continue
                superseded += result.notes_superseded
                print(
                    f"merge: {project}: {result.groups_applied} group(s), "
                    f"{result.notes_synthesized} synthesized, {result.notes_superseded} superseded"
                )
                continue
            # Gated apply.
            assert cases is not None  # set when gating
            try:
                groups = merger.propose(notes)
                accepted, verdicts = select_safe_groups(
                    store,
                    project,
                    groups,
                    cases,
                    machine_id=resolve_machine_id(),
                    model_label=merger.model_label,
                    k_gate=gate_k,
                )
                if accepted:
                    result = apply_groups(
                        store,
                        project,
                        accepted,
                        machine_id=resolve_machine_id(),
                        model_label=merger.model_label,
                    )
                    superseded += result.notes_superseded
            except Exception as exc:  # noqa: BLE001 - one project must not kill the run
                print(f"merge: {project}: failed ({exc}); skipped")
                continue
            rejected = [v for v in verdicts if not v.accepted]
            print(f"merge: {project}: {len(accepted)} group(s) applied, {len(rejected)} rejected")
            for v in rejected:
                if v.group.action == "keep":
                    desc = f"keep {v.group.keeper_id}"
                else:
                    desc = f"synthesize {v.group.title!r}"
                print(
                    f"merge: {project}: rejected {desc} "
                    f"(recall@{gate_k} {v.recall_before:.3f} -> {v.recall_after:.3f})"
                )
        if args.apply and superseded:
            if args.no_sync:
                store.reindex()
                print(f"merge: superseded {superseded} note(s); reindexed (no sync)")
            else:
                synced = _run_sync(store, _backend(store))
                print(
                    f"merge: superseded {superseded} note(s); "
                    f"synced (pushed={synced.pushed} pulled={synced.pulled})"
                )
    finally:
        store.close()
    return 0


def _eval_set_path(args: argparse.Namespace) -> Path:
    if args.eval_set:
        return Path(args.eval_set).expanduser()
    return resolve_home() / "eval" / "eval.jsonl"


def cmd_eval(args: argparse.Namespace) -> int:
    """Dispatch the eval subcommand (build | run | experiment)."""
    sub = getattr(args, "eval_command", None)
    if sub == "build":
        return _eval_build(args)
    if sub == "run":
        return _eval_run(args)
    if sub == "experiment":
        return _eval_experiment(args)
    print("eval: specify a subcommand: build | run | experiment")
    return 2


def _eval_build(args: argparse.Namespace) -> int:
    reflector = make_reflector()
    if reflector is None:
        print(
            "eval build: no reflection provider configured "
            "(set ANAMNESIS_REFLECTION_PROVIDER + model/base-url/key)"
        )
        return 0
    types = tuple(t.strip() for t in args.types.split(",") if t.strip())
    store = MemoryStore(resolve_home())
    try:
        cases = build_eval_candidates(
            store, reflector.client, reflector.model_label, types=types, n=args.n
        )
        added = append_candidates(_eval_set_path(args), cases)
        print(
            f"eval build: wrote {added} candidate(s) to {_eval_set_path(args)} "
            "(approved=false; curate before running)"
        )
    finally:
        store.close()
    return 0


def _eval_run(args: argparse.Namespace) -> int:
    path = _eval_set_path(args)
    if not path.exists():
        print(f"eval run: no eval set at {path} (run `anamnesis eval build` first)")
        return 2
    store = MemoryStore(resolve_home())
    try:
        cases, warnings = load_eval_set(
            path, store=store, include_unreviewed=args.include_unreviewed
        )
        for w in warnings:
            print(f"eval run: warning: {w}")
        report = run_baseline(store, cases)
        if args.as_json:
            print(json.dumps(baseline_to_dict(report), indent=2))
        else:
            print(render_baseline(report))
    finally:
        store.close()
    return 0


def _eval_experiment(args: argparse.Namespace) -> int:
    path = _eval_set_path(args)
    if not path.exists():
        print(f"eval experiment: no eval set at {path} (run `anamnesis eval build` first)")
        return 2
    if getattr(args, "as_merge", False):
        return _eval_experiment_merge(args, path)
    return _eval_experiment_reflect(args, path)


def _eval_experiment_reflect(args: argparse.Namespace, path: Path) -> int:
    reflector = make_reflector()
    if reflector is None:
        print(
            "eval experiment: no reflection provider configured "
            "(set ANAMNESIS_REFLECTION_PROVIDER + model/base-url/key)"
        )
        return 0
    store = MemoryStore(resolve_home())
    try:
        cases, warnings = load_eval_set(
            path, store=store, include_unreviewed=args.include_unreviewed
        )
        for w in warnings:
            print(f"eval experiment: warning: {w}")
        report = run_reflection_experiment(store, cases, reflector, machine_id=resolve_machine_id())
        print(render_experiment(report))
    finally:
        store.close()
    return 0


def _eval_experiment_merge(args: argparse.Namespace, path: Path) -> int:
    merger = make_merger()
    if merger is None:
        print(
            "eval experiment: no reflection provider configured "
            "(set ANAMNESIS_REFLECTION_PROVIDER + model/base-url/key)"
        )
        return 0
    store = MemoryStore(resolve_home())
    try:
        cases, warnings = load_eval_set(
            path, store=store, include_unreviewed=args.include_unreviewed
        )
        for w in warnings:
            print(f"eval experiment: warning: {w}")
        report = run_merge_experiment(store, cases, merger, machine_id=resolve_machine_id())
        print(render_merge_experiment(report))
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


def cmd_config(args: argparse.Namespace) -> int:
    """View or edit machine-local settings in config.json (no sync, no index touch)."""
    sub = args.config_command
    home = resolve_home()
    if sub == "list":
        view = config.settings_view()
        if args.as_json:
            print(json.dumps(view))
        else:
            print(_render_config(view))
        return 0
    if sub == "get":
        try:
            print(config.get_setting(args.key))
        except ValueError as exc:
            print(f"config: {exc}", file=sys.stderr)
            return 2
        return 0
    if sub == "set":
        pairs = args.pairs
        if len(pairs) % 2 != 0:
            print("config set: expected key value pairs", file=sys.stderr)
            return 2
        updates: dict[str, object] = {}
        for i in range(0, len(pairs), 2):
            key, raw = pairs[i], pairs[i + 1]
            try:
                updates[key] = config.validate_setting(key, raw)
            except ValueError as exc:
                print(f"config set: {exc}", file=sys.stderr)
                return 2
        config.update_store_config(home, updates)
        print(f"config: updated {', '.join(sorted(updates))}")
        return 0
    if sub == "unset":
        if args.key not in config.KNOWN_KEYS:
            print(f"config unset: unknown setting '{args.key}'", file=sys.stderr)
            return 2
        config.update_store_config(home, {args.key: config.UNSET})
        print(f"config: unset {args.key}")
        return 0
    if sub == "test":
        return _config_test()
    print("usage: anamnesis config {list|get|set|unset|test}", file=sys.stderr)
    return 2


def _render_config(view: dict[str, Any]) -> str:
    lines = []
    for key in ("machine_id", "remote"):
        field = view[key]
        lines.append(f"{key} = {field['value']!r}  [{field['source']}]")
    refl = view["reflection"]
    for key in ("provider", "model", "base_url", "timeout", "max_tokens"):
        field = refl[key]
        lines.append(f"reflection.{key} = {field['value']!r}  [{field['source']}]")
    preview = refl["api_key_preview"] or "(unset)"
    lines.append(f"reflection.api_key = {preview}  [{refl['api_key_source']}]")
    return "\n".join(lines)


def _config_test() -> int:
    """Verify the configured reflection provider with a minimal request."""
    ok, message = ping_reflection(config.resolve_reflection_settings())
    print(f"config test: {message}")
    return 0 if ok else 1


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
    if command == "merge":
        return cmd_merge(args)
    if command == "eval":
        return cmd_eval(args)
    if command == "import":
        return cmd_import(args)
    if command == "init":
        return cmd_init(args)
    if command == "config":
        return cmd_config(args)
    payload = read_hook_payload()
    if command == "inject":
        return cmd_inject(args, payload)
    if command == "capture":
        return cmd_capture(args, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
