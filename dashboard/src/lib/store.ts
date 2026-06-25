/**
 * Read/write orchestration over the local store. The dashboard is a thin client:
 * markdown files are the source of truth, the SQLite index and git history are
 * derived. Writes go markdown -> git commit (local) -> reindex via the Python
 * CLI, so the Python store stays the single indexer and the edit shows up in
 * history immediately. Sync (pull/push) is a separate, explicit action.
 */
import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";

import { ulid } from "ulid";

import { runCli } from "./cli";
import { localDir, memoryDir, resolveMachineId, scopeDir } from "./config";
import { closeDb, getMeta } from "./db";
import { commitPaths } from "./git";
import { notePath, parseMemory, serializeMemory } from "./markdown";
import { MEMORY_TYPES, type Memory, type MemoryType, type Scope } from "./types";

/** ISO-8601 to the second with a `+00:00` offset, matching Python's `_utcnow`. */
function utcNowSeconds(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");
}

/** Resolve a note's path relative to its tree from the index, falling back to disk.
 *
 * Portable notes live under `memory/`; machine-local notes under `local/`. The
 * returned path is relative to whichever tree holds the note.
 */
export function noteRelPath(id: string): string | null {
  const meta = getMeta(id);
  if (meta?.bodyPath) return meta.bodyPath;
  // Index missing/stale: look for the file under each type dir in BOTH trees.
  for (const base of [memoryDir(), localDir()]) {
    for (const t of MEMORY_TYPES) {
      if (fsSync.existsSync(path.join(base, notePath(t, id)))) {
        return notePath(t, id);
      }
    }
  }
  return null;
}

/** The absolute path of a note's markdown file, resolving its tree by scope. */
function noteAbsPath(id: string): string | null {
  const meta = getMeta(id);
  if (meta?.bodyPath) return path.join(scopeDir(meta.scope), meta.bodyPath);
  // Index missing/stale: search both trees for the file.
  for (const base of [memoryDir(), localDir()]) {
    for (const t of MEMORY_TYPES) {
      const abs = path.join(base, notePath(t, id));
      if (fsSync.existsSync(abs)) return abs;
    }
  }
  return null;
}

/** Read a note's raw markdown file text (the source of truth), or null. */
export async function readNoteText(id: string): Promise<string | null> {
  const abs = noteAbsPath(id);
  if (!abs) return null;
  try {
    return await fs.readFile(abs, "utf-8");
  } catch {
    return null;
  }
}

/** Read a note's full content from its markdown file (the source of truth). */
export async function readNote(id: string): Promise<Memory | null> {
  const text = await readNoteText(id);
  return text ? parseMemory(text) : null;
}

export interface WriteInput {
  /** Present when editing an existing note; absent when creating. */
  id?: string;
  type: MemoryType;
  title: string;
  body: string;
  project?: string;
  tags?: string[];
  scope?: Scope;
}

export interface WriteResult {
  memory: Memory;
  /** Short hash of the local commit, or null if not committed. */
  commit: string | null;
  reindexed: boolean;
}

/** Create a new note or update an existing one, then commit + reindex. */
export async function writeNote(input: WriteInput): Promise<WriteResult> {
  const now = utcNowSeconds();
  const existing = input.id ? await readNote(input.id) : null;
  if (input.id && !existing) {
    throw new Error(`note ${input.id} not found`);
  }

  const memory: Memory = {
    id: existing?.id ?? ulid(),
    type: input.type,
    title: input.title,
    body: input.body,
    project: input.project ?? existing?.project ?? "global",
    // Preserve the machine of origin on edit; stamp this machine on create.
    machineId: existing?.machineId ?? resolveMachineId(),
    scope: input.scope ?? existing?.scope ?? "portable",
    tags: input.tags ?? existing?.tags ?? [],
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
    provSource: existing?.provSource ?? "human",
    provModel: existing?.provModel ?? "",
    provSession: existing?.provSession ?? "",
    confidence: existing?.confidence ?? 1.0,
    supersedes: existing?.supersedes ?? [],
  };

  const rel = notePath(memory.type, memory.id);
  const abs = path.join(scopeDir(memory.scope), rel);
  await fs.mkdir(path.dirname(abs), { recursive: true });
  await fs.writeFile(abs, serializeMemory(memory), "utf-8");

  // Only files in the synced memory/ tree are committed; machine-local notes
  // live under local/ and are never committed, so they never leave the machine.
  const toCommit: string[] = [];
  if (memory.scope === "portable") toCommit.push(rel);
  // If the type or scope changed on edit, the file moved; drop the old one.
  if (existing && (existing.type !== memory.type || existing.scope !== memory.scope)) {
    const oldRel = notePath(existing.type, memory.id);
    await fs.rm(path.join(scopeDir(existing.scope), oldRel), { force: true });
    if (existing.scope === "portable") toCommit.push(oldRel); // commit removal of the synced file
  }

  const verb = existing ? "edit" : "create";
  let commit: string | null = null;
  if (toCommit.length > 0) {
    try {
      commit = await commitPaths(toCommit, `anamnesis: ${verb} ${memory.type} note via dashboard`);
    } catch {
      commit = null; // not a git repo, or nothing to commit; the write still stands
    }
  }

  const reindexed = await reindex();
  return { memory, commit, reindexed };
}

/** Mark a note reviewed by appending the `reviewed` tag (idempotent). Preserves provenance. */
export async function markReviewed(id: string): Promise<WriteResult> {
  const existing = await readNote(id);
  if (!existing) throw new Error(`note ${id} not found`);
  if (existing.tags.includes("reviewed")) {
    return { memory: existing, commit: null, reindexed: true };
  }
  return writeNote({
    id,
    type: existing.type,
    title: existing.title,
    body: existing.body,
    project: existing.project,
    tags: [...existing.tags, "reviewed"],
    scope: existing.scope,
  });
}

/** Delete a note: remove its markdown file, commit the removal if portable, reindex. */
export async function deleteNote(
  id: string,
): Promise<{ deleted: boolean; commit: string | null; reindexed: boolean }> {
  const existing = await readNote(id);
  if (!existing) throw new Error(`note ${id} not found`);
  const rel = notePath(existing.type, id);
  await fs.rm(path.join(scopeDir(existing.scope), rel), { force: true });

  let commit: string | null = null;
  if (existing.scope === "portable") {
    try {
      commit = await commitPaths([rel], `anamnesis: delete ${existing.type} note via dashboard`);
    } catch {
      commit = null; // not a git repo, or nothing to commit; the file is already gone
    }
  }
  const reindexed = await reindex();
  return { deleted: true, commit, reindexed };
}

/** Rebuild the SQLite index from markdown via `anamnesis reindex`. Returns true on success. */
export async function reindex(): Promise<boolean> {
  try {
    await runCli(["reindex"]);
    closeDb(); // force the next read to reopen the freshly-rebuilt index
    return true;
  } catch {
    return false;
  }
}

export interface SyncOutcome {
  ok: boolean;
  pushed: boolean;
  pulled: number;
  conflicted: boolean;
  head: string;
  detail: string;
  raw: string;
}

export interface CliRun {
  ok: boolean;
  /** Combined stdout+stderr, trimmed; shown verbatim in the UI. */
  output: string;
}

/** Run a CLI command and capture its output. `refresh` drops the cached index after a mutation. */
async function runCliText(args: string[], refresh: boolean): Promise<CliRun> {
  try {
    const { stdout, stderr } = await runCli(args);
    if (refresh) closeDb();
    return { ok: true, output: (stdout + stderr).trim() };
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string; message?: string };
    return {
      ok: false,
      output: ((e.stdout || "") + (e.stderr || "") || e.message || "command failed").trim(),
    };
  }
}

/** Run `anamnesis reflect` (dry-run unless apply). With apply, uses --no-sync and reindexes. */
export async function reflect(opts: { project?: string; apply?: boolean } = {}): Promise<CliRun> {
  const args = ["reflect"];
  if (opts.project) args.push("--project", opts.project);
  if (opts.apply) args.push("--apply", "--no-sync");
  return runCliText(args, opts.apply ?? false);
}

/** Run `anamnesis backfill-provenance` (dry-run unless apply). With apply, uses --no-sync. */
export async function backfillProvenance(opts: { apply?: boolean } = {}): Promise<CliRun> {
  const args = ["backfill-provenance"];
  if (opts.apply) args.push("--apply", "--no-sync");
  return runCliText(args, opts.apply ?? false);
}

/** Run one git sync cycle via `anamnesis sync` and parse the result line. */
export async function sync(): Promise<SyncOutcome> {
  let raw = "";
  try {
    const { stdout } = await runCli(["sync"]);
    raw = stdout.trim();
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string; message?: string };
    raw = (e.stdout || "") + (e.stderr || "") || e.message || "sync failed";
    closeDb();
    return {
      ok: false,
      pushed: false,
      pulled: 0,
      conflicted: /conflict/i.test(raw),
      head: "",
      detail: raw,
      raw,
    };
  }
  closeDb();
  const pushed = /pushed=True/.test(raw);
  const conflicted = /conflicted=True/.test(raw) || /conflict/i.test(raw);
  const pulled = Number(raw.match(/pulled=(\d+)/)?.[1] ?? 0);
  const head = raw.match(/head=(\S+)/)?.[1] ?? "";
  const detail = raw.match(/\(([^)]*)\)\s*$/)?.[1] ?? raw;
  return { ok: !conflicted, pushed, pulled, conflicted, head, detail, raw };
}
