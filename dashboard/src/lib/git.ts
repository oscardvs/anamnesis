/**
 * Read (and minimally write) the memory repo via git.
 *
 * `memory/` is a git repo; its history IS the memory history (architecture §4).
 * Sync commits are stamped by the Python backend (`sync.py`) with author
 * `anamnesis <anamnesis@<machine_id>>` and subject
 * `anamnesis: sync from <machine_id> at <ts>`, so the fleet view is derived
 * straight from authorship. Everything here is read-only except `commitPaths`,
 * which the dashboard uses to record an edit (architecture: edits write back to
 * the repo, then re-index).
 */
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { memoryDir, resolveMachineId } from "./config";
import type { Commit, MachineInfo, NoteCommit, RepoState } from "./types";

const execFileAsync = promisify(execFile);

const US = "\x1f"; // unit separator between fields
const COMMIT_FMT = `%H${US}%h${US}%an${US}%ae${US}%aI${US}%s`;
const MAX_BUFFER = 64 * 1024 * 1024;

/** Run a git command in the memory repo and return stdout (trimmed of trailing newline). */
export async function runGit(args: string[], home?: string): Promise<string> {
  const dir = memoryDir(home ?? undefined);
  const { stdout } = await execFileAsync("git", ["-C", dir, ...args], {
    maxBuffer: MAX_BUFFER,
    env: { ...process.env, GIT_OPTIONAL_LOCKS: "0" },
  });
  return stdout.replace(/\n$/, "");
}

/** Like {@link runGit} but never throws: returns "" on any git error. */
async function runGitSafe(args: string[], home?: string): Promise<string> {
  try {
    return await runGit(args, home);
  } catch {
    return "";
  }
}

/** Machine id encoded in an `anamnesis@<machine_id>` author email (else the email itself). */
function machineFromEmail(email: string): string {
  const at = email.indexOf("@");
  return at >= 0 ? email.slice(at + 1) : email;
}

function parseCommitLine(line: string): Commit | null {
  const parts = line.split(US);
  if (parts.length < 6) return null;
  const [hash, shortHash, author, email, date, ...subjectParts] = parts;
  return {
    hash,
    shortHash,
    author,
    email,
    machineId: machineFromEmail(email),
    date,
    subject: subjectParts.join(US),
  };
}

/** True if `memory/` is an initialized git repo with at least one commit. */
export async function hasHistory(home?: string): Promise<boolean> {
  const out = await runGitSafe(["rev-parse", "--verify", "--quiet", "HEAD"], home);
  return out.trim().length > 0;
}

/** The global commit history, newest first. */
export async function globalHistory(limit = 200, home?: string): Promise<Commit[]> {
  const out = await runGitSafe(["log", `--max-count=${limit}`, `--pretty=format:${COMMIT_FMT}`], home);
  if (!out) return [];
  return out
    .split("\n")
    .map(parseCommitLine)
    .filter((c): c is Commit => c !== null);
}

/** Commit history for a single note path (follows renames), newest first. */
export async function noteHistory(relPath: string, home?: string): Promise<NoteCommit[]> {
  const out = await runGitSafe(
    ["log", "--follow", `--format=__C__${US}${COMMIT_FMT}`, "--name-status", "--", relPath],
    home,
  );
  if (!out) return [];
  const commits: NoteCommit[] = [];
  let current: NoteCommit | null = null;
  for (const line of out.split("\n")) {
    if (line.startsWith(`__C__${US}`)) {
      const base = parseCommitLine(line.slice(`__C__${US}`.length));
      if (base) {
        current = { ...base, changeType: "M" };
        commits.push(current);
      } else {
        current = null;
      }
    } else if (current && /^[AMDRT]/.test(line)) {
      current.changeType = line[0];
    }
  }
  return commits;
}

/** A note's content at a given commit, or null if it did not exist then. */
export async function noteContentAtCommit(
  hash: string,
  relPath: string,
  home?: string,
): Promise<string | null> {
  try {
    return await runGit(["show", `${hash}:${relPath}`], home);
  } catch {
    return null;
  }
}

/** The unified diff a single commit introduced for a note. */
export async function commitDiff(hash: string, relPath: string, home?: string): Promise<string> {
  return runGitSafe(["show", "--no-color", `--format=`, hash, "--", relPath], home);
}

export interface CommitFile {
  changeType: string;
  path: string;
}

/** The note files a commit touched, with their change type. */
export async function commitFiles(hash: string, home?: string): Promise<CommitFile[]> {
  const out = await runGitSafe(["show", "--no-color", "--name-status", "--format=", hash], home);
  if (!out) return [];
  const files: CommitFile[] = [];
  for (const line of out.split("\n")) {
    if (!line.trim()) continue;
    const m = line.match(/^([AMDRT])\S*\t(.+)$/);
    if (m) {
      const cols = m[2].split("\t");
      files.push({ changeType: m[1], path: cols[cols.length - 1] });
    }
  }
  return files;
}

/** Per-machine view derived from commit authorship: last sync + last commit. */
export async function machinesFromGit(home?: string): Promise<Map<string, { lastSync: string; lastCommit: string }>> {
  const out = await runGitSafe(["log", `--pretty=format:${COMMIT_FMT}`], home);
  const map = new Map<string, { lastSync: string; lastCommit: string }>();
  if (!out) return map;
  for (const line of out.split("\n")) {
    const c = parseCommitLine(line);
    if (!c) continue;
    // log is newest-first, so the first time we see a machine is its latest commit.
    if (!map.has(c.machineId)) {
      map.set(c.machineId, { lastSync: c.date, lastCommit: c.shortHash });
    }
  }
  return map;
}

/** Merge git authorship with per-machine note counts into the fleet view. */
export async function fleet(noteCounts: Record<string, number>, home?: string): Promise<MachineInfo[]> {
  const git = await machinesFromGit(home);
  const current = resolveMachineId();
  const ids = new Set<string>([...git.keys(), ...Object.keys(noteCounts), current]);
  const machines: MachineInfo[] = [...ids].map((machineId) => {
    const g = git.get(machineId);
    return {
      machineId,
      noteCount: noteCounts[machineId] ?? 0,
      lastSync: g?.lastSync ?? null,
      lastCommit: g?.lastCommit ?? null,
      isCurrent: machineId === current,
    };
  });
  // Most recently active first; machines that never committed sort last.
  machines.sort((a, b) => (b.lastSync ?? "").localeCompare(a.lastSync ?? ""));
  return machines;
}

/** Working-tree / sync state of the memory repo (dirty, ahead/behind, conflicts). */
export async function repoState(home?: string): Promise<RepoState> {
  const initialized = (await runGitSafe(["rev-parse", "--is-inside-work-tree"], home)) === "true";
  if (!initialized) {
    return {
      initialized: false,
      remote: null,
      head: "",
      dirty: false,
      ahead: 0,
      behind: 0,
      conflicted: false,
      conflictedPaths: [],
    };
  }
  const head = await runGitSafe(["rev-parse", "--short", "HEAD"], home);
  const remote = (await runGitSafe(["remote", "get-url", "origin"], home)) || null;
  const porcelain = await runGitSafe(["status", "--porcelain"], home);
  const lines = porcelain ? porcelain.split("\n").filter(Boolean) : [];
  const dirty = lines.length > 0;
  // Conflict states in porcelain v1: UU, AA, DD, AU, UA, DU, UD.
  const conflictCodes = new Set(["UU", "AA", "DD", "AU", "UA", "DU", "UD"]);
  const conflictedPaths = lines
    .filter((l) => conflictCodes.has(l.slice(0, 2)))
    .map((l) => l.slice(3));
  let ahead = 0;
  let behind = 0;
  if (remote) {
    const counts = await runGitSafe(["rev-list", "--left-right", "--count", "origin/main...HEAD"], home);
    const m = counts.match(/^(\d+)\s+(\d+)$/);
    if (m) {
      behind = Number(m[1]);
      ahead = Number(m[2]);
    }
  }
  return {
    initialized: true,
    remote,
    head,
    dirty,
    ahead,
    behind,
    conflicted: conflictedPaths.length > 0,
    conflictedPaths,
  };
}

/** Stage and commit specific paths with the anamnesis identity (matches sync.py). */
export async function commitPaths(
  relPaths: string[],
  message: string,
  home?: string,
): Promise<string> {
  const machineId = resolveMachineId();
  const dir = memoryDir(home ?? undefined);
  const ident = {
    GIT_AUTHOR_NAME: "anamnesis",
    GIT_AUTHOR_EMAIL: `anamnesis@${machineId}`,
    GIT_COMMITTER_NAME: "anamnesis",
    GIT_COMMITTER_EMAIL: `anamnesis@${machineId}`,
  };
  await execFileAsync("git", ["-C", dir, "add", "--", ...relPaths], { maxBuffer: MAX_BUFFER });
  await execFileAsync("git", ["-C", dir, "commit", "-m", message], {
    maxBuffer: MAX_BUFFER,
    env: { ...process.env, ...ident },
  });
  return runGit(["rev-parse", "--short", "HEAD"], home);
}
