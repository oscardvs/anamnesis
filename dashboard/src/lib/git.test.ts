import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  commitFiles,
  commitPaths,
  fleet,
  globalHistory,
  hasHistory,
  machinesFromGit,
  noteContentAtCommit,
  noteHistory,
  repoState,
} from "./git";

// These exercise the real git plumbing against throwaway repos: no mocks, no
// personal data. memory/ under a temp home is a git repo, exactly as on disk.

let home: string;
let mem: string;
const savedMachine = process.env.ANAMNESIS_MACHINE_ID;

function git(...args: string[]): string {
  return execFileSync("git", ["-C", mem, ...args], { encoding: "utf-8" }).trim();
}

function gitTry(...args: string[]): void {
  try {
    execFileSync("git", ["-C", mem, ...args], { stdio: "ignore" });
  } catch {
    /* expected to fail (e.g. a conflicting merge) */
  }
}

/** Commit a file as a given machine, matching sync.py's anamnesis identity + a fixed date. */
function commitAs(machineId: string, relPath: string, content: string, subject: string, isoDate: string): void {
  const abs = path.join(mem, relPath);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, content);
  execFileSync("git", ["-C", mem, "add", "--", relPath]);
  execFileSync("git", ["-C", mem, "commit", "-m", subject], {
    env: {
      ...process.env,
      GIT_AUTHOR_NAME: "anamnesis",
      GIT_AUTHOR_EMAIL: `anamnesis@${machineId}`,
      GIT_COMMITTER_NAME: "anamnesis",
      GIT_COMMITTER_EMAIL: `anamnesis@${machineId}`,
      GIT_AUTHOR_DATE: isoDate,
      GIT_COMMITTER_DATE: isoDate,
    },
  });
}

beforeEach(() => {
  home = fs.mkdtempSync(path.join(os.tmpdir(), "anamnesis-git-"));
  mem = path.join(home, "memory");
  fs.mkdirSync(mem);
  execFileSync("git", ["-C", mem, "init", "-b", "main"], { stdio: "ignore" });
  // A fallback identity for setup commits where machine attribution is irrelevant.
  git("config", "user.email", "dev@test.invalid");
  git("config", "user.name", "test");
});

afterEach(() => {
  fs.rmSync(home, { recursive: true, force: true });
  if (savedMachine === undefined) delete process.env.ANAMNESIS_MACHINE_ID;
  else process.env.ANAMNESIS_MACHINE_ID = savedMachine;
});

describe("git history", () => {
  it("reports no history on a fresh repo, then history after a commit", async () => {
    expect(await hasHistory(home)).toBe(false);
    commitAs("m1", "semantic/a.md", "one\n", "first", "2026-06-01T10:00:00+00:00");
    expect(await hasHistory(home)).toBe(true);
  });

  it("returns the global history newest-first with the machine id parsed from the author email", async () => {
    commitAs("m1", "semantic/a.md", "one\n", "first", "2026-06-01T10:00:00+00:00");
    commitAs("m2", "semantic/b.md", "two\n", "second", "2026-06-02T10:00:00+00:00");
    const log = await globalHistory(10, home);
    expect(log.map((c) => c.subject)).toEqual(["second", "first"]);
    expect(log[0].machineId).toBe("m2");
    expect(log[1].machineId).toBe("m1");
    expect(log[0].shortHash).toHaveLength(7);
  });

  it("annotates a single note's history with the change type", async () => {
    commitAs("m1", "semantic/h.md", "v1\n", "add", "2026-06-01T10:00:00+00:00");
    commitAs("m1", "semantic/h.md", "v2\n", "modify", "2026-06-02T10:00:00+00:00");
    const hist = await noteHistory("semantic/h.md", home);
    expect(hist).toHaveLength(2);
    expect(hist[0].changeType).toBe("M");
    expect(hist[1].changeType).toBe("A");
  });

  it("reads a note's content at a past commit", async () => {
    commitAs("m1", "semantic/h.md", "old\n", "add", "2026-06-01T10:00:00+00:00");
    const first = (await globalHistory(10, home))[0].hash;
    commitAs("m1", "semantic/h.md", "new\n", "modify", "2026-06-02T10:00:00+00:00");
    // runGit trims the trailing newline from `git show` output.
    expect(await noteContentAtCommit(first, "semantic/h.md", home)).toBe("old");
    expect(await noteContentAtCommit("deadbeef", "semantic/h.md", home)).toBeNull();
  });

  it("lists the files a commit touched with their change type", async () => {
    commitAs("m1", "semantic/a.md", "x\n", "add a", "2026-06-01T10:00:00+00:00");
    const files = await commitFiles((await globalHistory(10, home))[0].hash, home);
    expect(files).toEqual([{ changeType: "A", path: "semantic/a.md" }]);
  });
});

describe("fleet derivation", () => {
  it("tracks each machine's latest sync + commit from authorship", async () => {
    commitAs("desktop", "semantic/a.md", "1\n", "a", "2026-06-01T10:00:00+00:00");
    commitAs("laptop", "semantic/b.md", "2\n", "b", "2026-06-03T10:00:00+00:00");
    commitAs("desktop", "semantic/c.md", "3\n", "c", "2026-06-02T10:00:00+00:00");
    const map = await machinesFromGit(home);
    // each machine's most recent commit wins: laptop's only commit (06-03),
    // desktop's newest of its two (06-02, not the earlier 06-01).
    expect(map.get("laptop")?.lastSync).toBe("2026-06-03T10:00:00+00:00");
    expect(map.get("desktop")?.lastSync).toBe("2026-06-02T10:00:00+00:00");
  });

  it("merges note counts, flags the current machine, and sorts most-recent-first", async () => {
    process.env.ANAMNESIS_MACHINE_ID = "desktop";
    commitAs("desktop", "semantic/a.md", "1\n", "a", "2026-06-01T10:00:00+00:00");
    commitAs("laptop", "semantic/b.md", "2\n", "b", "2026-06-03T10:00:00+00:00");
    // "archived" has notes in the index but never committed.
    const machines = await fleet({ desktop: 5, laptop: 2, archived: 1 }, home);
    expect(machines.map((m) => m.machineId)).toEqual(["laptop", "desktop", "archived"]);
    const desktop = machines.find((m) => m.machineId === "desktop")!;
    expect(desktop.isCurrent).toBe(true);
    expect(desktop.noteCount).toBe(5);
    const archived = machines.find((m) => m.machineId === "archived")!;
    expect(archived.lastSync).toBeNull();
    expect(archived.noteCount).toBe(1);
  });
});

describe("repo state", () => {
  it("reports a clean repo with a head and no conflicts", async () => {
    commitAs("m1", "semantic/a.md", "x\n", "a", "2026-06-01T10:00:00+00:00");
    const state = await repoState(home);
    expect(state.initialized).toBe(true);
    expect(state.dirty).toBe(false);
    expect(state.conflicted).toBe(false);
    expect(state.head).toHaveLength(7);
  });

  it("counts commits ahead of the tracked remote", async () => {
    const bare = path.join(home, "remote.git");
    execFileSync("git", ["init", "--bare", "-b", "main", bare], { stdio: "ignore" });
    commitAs("m1", "semantic/a.md", "x\n", "a", "2026-06-01T10:00:00+00:00");
    git("remote", "add", "origin", bare);
    git("push", "-q", "-u", "origin", "main");
    commitAs("m1", "semantic/a.md", "y\n", "b", "2026-06-02T10:00:00+00:00");
    const state = await repoState(home);
    expect(state.remote).toBe(bare);
    expect(state.ahead).toBe(1);
    expect(state.behind).toBe(0);
  });

  it("surfaces an unresolved merge conflict with the conflicted paths", async () => {
    commitAs("m1", "semantic/a.md", "base\n", "base", "2026-06-01T10:00:00+00:00");
    git("checkout", "-q", "-b", "other");
    commitAs("m1", "semantic/a.md", "other side\n", "other", "2026-06-02T10:00:00+00:00");
    git("checkout", "-q", "main");
    commitAs("m1", "semantic/a.md", "main side\n", "main", "2026-06-02T11:00:00+00:00");
    gitTry("merge", "other");
    const state = await repoState(home);
    expect(state.conflicted).toBe(true);
    expect(state.conflictedPaths).toEqual(["semantic/a.md"]);
    expect(state.dirty).toBe(true);
  });
});

describe("commitPaths", () => {
  it("commits with the anamnesis@<machine> identity and returns the short hash", async () => {
    process.env.ANAMNESIS_MACHINE_ID = "cpmachine";
    fs.mkdirSync(path.join(mem, "semantic"), { recursive: true });
    fs.writeFileSync(path.join(mem, "semantic/c.md"), "hello\n");
    const short = await commitPaths(["semantic/c.md"], "anamnesis: create via dashboard", home);
    expect(short).toBe(git("rev-parse", "--short", "HEAD"));
    expect(git("log", "-1", "--format=%ae")).toBe("anamnesis@cpmachine");
    expect(git("log", "-1", "--format=%s")).toBe("anamnesis: create via dashboard");
  });
});
