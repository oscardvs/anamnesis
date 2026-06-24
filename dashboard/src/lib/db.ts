/**
 * Read-only access to the derived SQLite index (WAL + FTS5).
 *
 * The index is owned and written by the Python store; the dashboard only reads
 * it for search/list (architecture: the DB is derived and rebuildable, never
 * the source of truth). We open read-only, set a busy_timeout to tolerate the
 * writer's checkpoints, and never change journal_mode. Reading the index
 * directly (vs shelling out to Python) avoids a process spawn per request and
 * keeps search/list latency low.
 */
import fs from "node:fs";

import Database from "better-sqlite3";

import { dbPath } from "./config";
import type { MemoryMeta, MemoryType, ProvSource, Scope, StoreStats } from "./types";

const TAG_SEP = "\x1f";

type DbHandle = import("better-sqlite3").Database;

// Cache the connection across HMR reloads in dev, alongside the index file's
// signature. A long-lived always-on dashboard (the tailnet hub) reads an index
// that other processes write to (the MCP server's memory_write, the capture
// hook, sync pulling notes from other machines). Tracking the file signature
// lets us reopen when it changes, so external writes show up without a restart.
const globalForDb = globalThis as unknown as {
  __anamnesisDb?: DbHandle | null;
  __anamnesisDbSig?: string;
};

/** mtime+size of the index file and its -wal sidecar; changes on any write. */
function indexSignature(path: string): string {
  const parts: string[] = [];
  for (const p of [path, `${path}-wal`]) {
    try {
      const st = fs.statSync(p);
      parts.push(`${st.mtimeMs}:${st.size}`);
    } catch {
      parts.push("-"); // the -wal sidecar may not exist between checkpoints
    }
  }
  return parts.join("|");
}

/** Open (or reuse) the read-only index connection, reopening if the file changed. */
function getDb(): DbHandle | null {
  const path = dbPath();
  if (!fs.existsSync(path)) {
    if (globalForDb.__anamnesisDb) {
      try {
        globalForDb.__anamnesisDb.close();
      } catch {
        /* ignore */
      }
    }
    globalForDb.__anamnesisDb = null;
    globalForDb.__anamnesisDbSig = undefined;
    return null;
  }
  const sig = indexSignature(path);
  if (globalForDb.__anamnesisDb && globalForDb.__anamnesisDbSig === sig) {
    return globalForDb.__anamnesisDb;
  }
  // First open, or the index changed under us: (re)open against current state.
  // Queries run synchronously, so we can close the stale handle safely here.
  if (globalForDb.__anamnesisDb) {
    try {
      globalForDb.__anamnesisDb.close();
    } catch {
      /* ignore */
    }
  }
  const db = new Database(path, { readonly: true, fileMustExist: true });
  db.pragma("busy_timeout = 5000");
  globalForDb.__anamnesisDb = db;
  globalForDb.__anamnesisDbSig = sig;
  return db;
}

/** Drop the cached connection so the next read reopens (call after a reindex). */
export function closeDb(): void {
  if (globalForDb.__anamnesisDb) {
    try {
      globalForDb.__anamnesisDb.close();
    } catch {
      /* ignore */
    }
  }
  globalForDb.__anamnesisDb = undefined;
  globalForDb.__anamnesisDbSig = undefined;
}

/** True if the index file exists and is readable. */
export function indexExists(): boolean {
  return getDb() !== null;
}

/**
 * Turn free text into a safe FTS5 MATCH expression: each word becomes a quoted
 * phrase, terms ANDed. This mirrors the Python `_fts_query` and neutralizes
 * every FTS5 operator (AND/OR/NOT/NEAR, `*`, `:`, `"`) so arbitrary input can
 * never break the query parser. Returns "" when there are no word tokens.
 */
export function buildMatch(query: string): string {
  const tokens = query.match(/[\p{L}\p{N}_]+/gu) ?? [];
  return tokens.map((t) => `"${t}"`).join(" AND ");
}

const SELECT_META = `
  SELECT m.id, m.type, m.title, m.body_path AS bodyPath, m.project,
         m.machine_id AS machineId, m.scope, m.created_at AS createdAt,
         m.updated_at AS updatedAt,
         m.prov_source AS provSource, m.confidence, m.prov_model AS provModel,
         (SELECT group_concat(tag, char(31)) FROM memory_tags t WHERE t.memory_id = m.id) AS tagStr
`;

interface MetaRow {
  id: string;
  type: string;
  title: string;
  bodyPath: string;
  project: string;
  machineId: string;
  scope: string;
  createdAt: string;
  updatedAt: string;
  provSource: string;
  confidence: number;
  provModel: string | null;
  tagStr: string | null;
}

function toMeta(row: MetaRow): MemoryMeta {
  return {
    id: row.id,
    type: row.type as MemoryType,
    title: row.title,
    bodyPath: row.bodyPath,
    project: row.project,
    machineId: row.machineId,
    scope: row.scope as Scope,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    provSource: row.provSource as ProvSource,
    confidence: row.confidence,
    provModel: row.provModel ?? "",
    tags: row.tagStr ? row.tagStr.split(TAG_SEP) : [],
  };
}

export interface ListOpts {
  project?: string;
  type?: MemoryType;
  provSource?: ProvSource;
  excludeTag?: string;
  limit?: number;
  offset?: number;
}

/** List note metadata (newest first), optionally scoped by project/type. */
export function listMeta(opts: ListOpts = {}): MemoryMeta[] {
  const db = getDb();
  if (!db) return [];
  const where: string[] = [];
  const params: unknown[] = [];
  if (opts.project) {
    where.push("m.project = ?");
    params.push(opts.project);
  }
  if (opts.type) {
    where.push("m.type = ?");
    params.push(opts.type);
  }
  if (opts.provSource) {
    where.push("m.prov_source = ?");
    params.push(opts.provSource);
  }
  if (opts.excludeTag) {
    where.push("m.id NOT IN (SELECT memory_id FROM memory_tags WHERE tag = ?)");
    params.push(opts.excludeTag);
  }
  const sql = [
    SELECT_META,
    "FROM memories m",
    where.length ? "WHERE " + where.join(" AND ") : "",
    "ORDER BY m.updated_at DESC, m.id DESC",
    "LIMIT ? OFFSET ?",
  ].join("\n");
  params.push(opts.limit ?? 200, opts.offset ?? 0);
  return (db.prepare(sql).all(...params) as MetaRow[]).map(toMeta);
}

/** Keyword (FTS5 BM25) search over the index, optionally scoped. */
export function searchMeta(query: string, opts: ListOpts = {}): MemoryMeta[] {
  const db = getDb();
  if (!db) return [];
  const match = buildMatch(query);
  if (!match) return [];
  const where: string[] = ["memories_fts MATCH ?"];
  const params: unknown[] = [match];
  if (opts.project) {
    where.push("m.project = ?");
    params.push(opts.project);
  }
  if (opts.type) {
    where.push("m.type = ?");
    params.push(opts.type);
  }
  if (opts.provSource) {
    where.push("m.prov_source = ?");
    params.push(opts.provSource);
  }
  if (opts.excludeTag) {
    where.push("m.id NOT IN (SELECT memory_id FROM memory_tags WHERE tag = ?)");
    params.push(opts.excludeTag);
  }
  const sql = [
    SELECT_META,
    "FROM memories_fts f JOIN memories m ON m.id = f.id",
    "WHERE " + where.join(" AND "),
    "ORDER BY bm25(memories_fts), m.updated_at DESC",
    "LIMIT ?",
  ].join("\n");
  params.push(opts.limit ?? 50);
  return (db.prepare(sql).all(...params) as MetaRow[]).map(toMeta);
}

/** Metadata for one note, or null if not indexed. */
export function getMeta(id: string): MemoryMeta | null {
  const db = getDb();
  if (!db) return null;
  const row = db.prepare(`${SELECT_META} FROM memories m WHERE m.id = ?`).get(id) as
    | MetaRow
    | undefined;
  return row ? toMeta(row) : null;
}

/** How many reflection notes are still awaiting human review (not tagged `reviewed`). */
export function countPendingReflections(): number {
  const db = getDb();
  if (!db) return 0;
  const row = db
    .prepare(
      "SELECT COUNT(*) AS c FROM memories WHERE prov_source = 'reflection' " +
        "AND id NOT IN (SELECT memory_id FROM memory_tags WHERE tag = 'reviewed')",
    )
    .get() as { c: number };
  return row.c;
}

/** Aggregate counts (total, by type, by project), mirroring `StoreStats`. */
export function stats(): StoreStats {
  const db = getDb();
  if (!db) return { total: 0, byType: {}, byProject: {} };
  const total = (db.prepare("SELECT COUNT(*) AS c FROM memories").get() as { c: number }).c;
  const byType: Record<string, number> = {};
  for (const r of db.prepare("SELECT type, COUNT(*) AS c FROM memories GROUP BY type").all() as {
    type: string;
    c: number;
  }[]) {
    byType[r.type] = r.c;
  }
  const byProject: Record<string, number> = {};
  for (const r of db
    .prepare("SELECT project, COUNT(*) AS c FROM memories GROUP BY project ORDER BY c DESC")
    .all() as { project: string; c: number }[]) {
    byProject[r.project] = r.c;
  }
  return { total, byType, byProject };
}

/** Note counts grouped by machine id (for the fleet view). */
export function countsByMachine(): Record<string, number> {
  const db = getDb();
  if (!db) return {};
  const out: Record<string, number> = {};
  for (const r of db
    .prepare("SELECT machine_id AS machineId, COUNT(*) AS c FROM memories GROUP BY machine_id")
    .all() as { machineId: string; c: number }[]) {
    out[r.machineId] = r.c;
  }
  return out;
}
