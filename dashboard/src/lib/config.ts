/**
 * Store-location config for the dashboard.
 *
 * Mirrors `server/src/anamnesis/config.py`: the store root comes from
 * `ANAMNESIS_HOME` (default `~/.anamnesis`), and the machine id from
 * `ANAMNESIS_MACHINE_ID` (default hostname). The dashboard is a thin client
 * over that same on-disk store, so these must agree with the Python side.
 */
import os from "node:os";
import path from "node:path";

/** Expand a leading `~` to the user's home directory. */
function expandHome(p: string): string {
  if (p === "~") return os.homedir();
  if (p.startsWith("~/")) return path.join(os.homedir(), p.slice(2));
  return p;
}

/** Resolve the store root from `ANAMNESIS_HOME` (default `~/.anamnesis`). */
export function resolveHome(): string {
  const raw = process.env.ANAMNESIS_HOME;
  return raw ? path.resolve(expandHome(raw)) : path.join(os.homedir(), ".anamnesis");
}

/** The markdown source-of-truth directory (a git repo). */
export function memoryDir(home: string = resolveHome()): string {
  return path.join(home, "memory");
}

/** The derived SQLite index (WAL + FTS5). Never the source of truth. */
export function dbPath(home: string = resolveHome()): string {
  return path.join(home, "index.db");
}

/** This machine's id, used when the dashboard authors a git commit. */
export function resolveMachineId(): string {
  return process.env.ANAMNESIS_MACHINE_ID || os.hostname() || "unknown";
}
