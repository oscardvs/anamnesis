/**
 * Shared types mirroring the Python store (`server/src/anamnesis/store.py`).
 * The markdown front-matter is the source of truth; these shapes describe what
 * the dashboard reads back from the SQLite index and the markdown files.
 */

export type MemoryType = "procedural" | "semantic" | "episodic";
export type Scope = "portable" | "machine-local";

export type ProvSource = "human" | "session-end" | "reflection" | "import";

export const PROV_SOURCES: ProvSource[] = ["human", "session-end", "reflection", "import"];

export const MEMORY_TYPES: MemoryType[] = ["procedural", "semantic", "episodic"];

/** A full note: front-matter metadata plus the markdown body. */
export interface Memory {
  id: string;
  type: MemoryType;
  title: string;
  body: string;
  project: string;
  machineId: string;
  scope: Scope;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  /** How this note came to exist (architecture section 3). */
  provSource: ProvSource;
  /** Model that generated the note, if any (e.g. "deepseek/v4-flash"); "" otherwise. */
  provModel: string;
  /** Originating session id, if any; "" otherwise. */
  provSession: string;
  /** Trust weight: 1.0 for human, 0.6 for reflection. */
  confidence: number;
  /** Id of a prior note this revises, if any; "" otherwise. */
  supersedes: string;
}

/** A note's metadata as indexed in SQLite (no body; cheap to list/search). */
export interface MemoryMeta {
  id: string;
  type: MemoryType;
  title: string;
  project: string;
  machineId: string;
  scope: Scope;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  /** Path of the markdown file relative to `memory/`, e.g. `semantic/01J….md`. */
  bodyPath: string;
  provSource: ProvSource;
  confidence: number;
  provModel: string;
}

/** Aggregate counts surfaced on the overview, mirroring `StoreStats`. */
export interface StoreStats {
  total: number;
  byType: Record<string, number>;
  byProject: Record<string, number>;
}

/** One commit in the memory repo's history. */
export interface Commit {
  hash: string;
  shortHash: string;
  author: string;
  email: string;
  /** Machine id parsed from the `anamnesis@<machine_id>` author email. */
  machineId: string;
  date: string;
  subject: string;
}

/** A commit annotated with how it touched a particular note. */
export interface NoteCommit extends Commit {
  /** "A" added, "M" modified, "D" deleted, "R" renamed. */
  changeType: string;
}

/** A single machine in the fleet, derived from git authorship + the index. */
export interface MachineInfo {
  machineId: string;
  /** Notes currently attributed to this machine in the index. */
  noteCount: number;
  /** ISO timestamp of this machine's most recent sync commit, if any. */
  lastSync: string | null;
  /** Short hash of that machine's most recent commit. */
  lastCommit: string | null;
  /** True for the machine this dashboard is running on. */
  isCurrent: boolean;
}

/** Working-tree / sync state of the memory repo. */
export interface RepoState {
  initialized: boolean;
  remote: string | null;
  head: string;
  /** Uncommitted changes present. */
  dirty: boolean;
  /** Commits ahead of / behind the tracked remote branch. */
  ahead: number;
  behind: number;
  /** Unresolved merge/rebase conflict markers present in the tree. */
  conflicted: boolean;
  /** Paths with conflict markers, when `conflicted`. */
  conflictedPaths: string[];
}

/** One hunk line in a rendered diff. */
export interface DiffLine {
  type: "add" | "del" | "context" | "hunk";
  /** Line number in the old file (null for added/hunk lines). */
  oldNumber: number | null;
  /** Line number in the new file (null for deleted/hunk lines). */
  newNumber: number | null;
  content: string;
}

/** A computed diff for one file, with its change type and +/- counts. */
export interface FileDiff {
  path: string;
  changeType: string;
  additions: number;
  deletions: number;
  lines: DiffLine[];
}
