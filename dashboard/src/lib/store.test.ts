import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { closeDb } from "./db";
import { parseMemory, serializeMemory } from "./markdown";
import { deleteNote, markReviewed, readNote, reflect, writeNote } from "./store";

// writeNote orchestrates markdown write -> git commit -> reindex. We point the
// store at a temp home and stub the `anamnesis` CLI with `true` (exit 0, no
// output) so reindex succeeds without invoking Python; the markdown + git
// write-back are the logic under test. No personal data, no real corpus.

let home: string;
let mem: string;
const saved: Record<string, string | undefined> = {};

function git(...args: string[]): string {
  return execFileSync("git", ["-C", mem, ...args], { encoding: "utf-8" }).trim();
}

beforeEach(() => {
  home = fs.mkdtempSync(path.join(os.tmpdir(), "anamnesis-store-"));
  mem = path.join(home, "memory");
  fs.mkdirSync(mem);
  execFileSync("git", ["-C", mem, "init", "-b", "main"], { stdio: "ignore" });
  saved.home = process.env.ANAMNESIS_HOME;
  saved.machine = process.env.ANAMNESIS_MACHINE_ID;
  saved.cli = process.env.ANAMNESIS_CLI;
  process.env.ANAMNESIS_HOME = home;
  process.env.ANAMNESIS_MACHINE_ID = "testmachine";
  process.env.ANAMNESIS_CLI = "true"; // stub `anamnesis reindex` (no Python)
  closeDb(); // drop any cached index handle from a previous test
});

afterEach(() => {
  fs.rmSync(home, { recursive: true, force: true });
  for (const [k, key] of [
    ["home", "ANAMNESIS_HOME"],
    ["machine", "ANAMNESIS_MACHINE_ID"],
    ["cli", "ANAMNESIS_CLI"],
  ] as const) {
    if (saved[k] === undefined) delete process.env[key];
    else process.env[key] = saved[k];
  }
  closeDb();
});

describe("writeNote create", () => {
  it("writes the markdown file, commits it, and reports the reindex", async () => {
    const res = await writeNote({
      type: "semantic",
      title: "Hello",
      body: "world body",
      project: "demo",
      tags: ["t1"],
    });
    expect(res.memory.id).toMatch(/^[0-9A-HJKMNP-TV-Z]{26}$/); // ULID
    expect(res.commit).not.toBeNull();
    expect(res.reindexed).toBe(true);

    const file = path.join(mem, "semantic", `${res.memory.id}.md`);
    expect(fs.existsSync(file)).toBe(true);
    const parsed = parseMemory(fs.readFileSync(file, "utf-8"));
    expect(parsed.title).toBe("Hello");
    expect(parsed.body).toBe("world body");
    expect(parsed.project).toBe("demo");
    expect(parsed.machineId).toBe("testmachine");

    expect(git("log", "-1", "--format=%s")).toBe("anamnesis: create semantic note via dashboard");
    expect(git("log", "-1", "--format=%ae")).toBe("anamnesis@testmachine");
  });

  it("defaults project to global and scope to portable", async () => {
    const res = await writeNote({ type: "procedural", title: "T", body: "b" });
    expect(res.memory.project).toBe("global");
    expect(res.memory.scope).toBe("portable");
  });
});

describe("writeNote edit", () => {
  it("preserves id, createdAt, and machine of origin while updating content", async () => {
    const created = await writeNote({ type: "semantic", title: "Orig", body: "one" });
    const edited = await writeNote({
      id: created.memory.id,
      type: "semantic",
      title: "Edited",
      body: "two",
    });
    expect(edited.memory.id).toBe(created.memory.id);
    expect(edited.memory.createdAt).toBe(created.memory.createdAt);
    expect(edited.memory.machineId).toBe(created.memory.machineId);

    const reread = await readNote(created.memory.id);
    expect(reread?.title).toBe("Edited");
    expect(reread?.body).toBe("two");
    // create + edit = two commits
    expect(git("rev-list", "--count", "HEAD")).toBe("2");
  });

  it("moves the file between type dirs when the type changes", async () => {
    const created = await writeNote({ type: "semantic", title: "T", body: "b" });
    await writeNote({ id: created.memory.id, type: "procedural", title: "T", body: "b" });
    expect(fs.existsSync(path.join(mem, "procedural", `${created.memory.id}.md`))).toBe(true);
    expect(fs.existsSync(path.join(mem, "semantic", `${created.memory.id}.md`))).toBe(false);
  });

  it("throws when editing a note that does not exist", async () => {
    await expect(
      writeNote({ id: "01KV000000000000000000000X", type: "semantic", title: "x", body: "y" }),
    ).rejects.toThrow(/not found/);
  });
});

describe("readNote", () => {
  it("returns null for an unknown id", async () => {
    expect(await readNote("01KV000000000000000000000X")).toBeNull();
  });
});

describe("writeNote provenance", () => {
  it("preserves an existing note's provenance when the dashboard edits it", async () => {
    // Seed a reflection note directly on disk (the CLI, not the dashboard, makes these).
    const id = "01KV2V3G79X1VNYD9WC0Z83WDW";
    const file = path.join(mem, "semantic", `${id}.md`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(
      file,
      serializeMemory({
        id,
        type: "semantic",
        title: "Distilled fact",
        body: "prefer WAL",
        project: "demo",
        machineId: "testmachine",
        scope: "portable",
        tags: ["reflection"],
        createdAt: "2026-06-01T00:00:00+00:00",
        updatedAt: "2026-06-01T00:00:00+00:00",
        provSource: "reflection",
        provModel: "deepseek/v4-flash",
        provSession: "",
        confidence: 0.6,
        supersedes: "",
      }),
      "utf-8",
    );

    await writeNote({
      id,
      type: "semantic",
      title: "Distilled fact",
      body: "prefer WAL",
      project: "demo",
      tags: ["reflection", "reviewed"],
    });

    const reread = await readNote(id);
    expect(reread?.provSource).toBe("reflection");
    expect(reread?.provModel).toBe("deepseek/v4-flash");
    expect(reread?.confidence).toBe(0.6);
    expect(reread?.tags).toEqual(["reflection", "reviewed"]);
  });

  it("defaults new notes to human / confidence 1.0", async () => {
    const res = await writeNote({ type: "semantic", title: "t", body: "b" });
    expect(res.memory.provSource).toBe("human");
    expect(res.memory.confidence).toBe(1.0);
  });
});

describe("machine-local scope", () => {
  it("writes a machine-local note to local/ (not memory/) and does not commit it", async () => {
    const res = await writeNote({
      type: "semantic",
      title: "local only",
      body: "secret",
      project: "p",
      scope: "machine-local",
    });
    expect(res.memory.scope).toBe("machine-local");
    expect(res.commit).toBeNull(); // local notes are never git-committed
    expect(fs.existsSync(path.join(home, "local", "semantic", `${res.memory.id}.md`))).toBe(true);
    expect(fs.existsSync(path.join(mem, "semantic", `${res.memory.id}.md`))).toBe(false);

    const got = await readNote(res.memory.id);
    expect(got?.body).toBe("secret");
    expect(got?.scope).toBe("machine-local");
  });

  it("keeps portable notes in memory/ and commits them", async () => {
    const res = await writeNote({ type: "semantic", title: "shared", body: "b", project: "p" });
    expect(res.memory.scope).toBe("portable");
    expect(res.commit).not.toBeNull();
    expect(fs.existsSync(path.join(mem, "semantic", `${res.memory.id}.md`))).toBe(true);
    expect(fs.existsSync(path.join(home, "local", "semantic", `${res.memory.id}.md`))).toBe(false);
  });
});

describe("markReviewed", () => {
  it("adds the reviewed tag while preserving provenance", async () => {
    const id = "01KV2V3G79X1VNYD9WC0Z83WDW";
    const file = path.join(mem, "semantic", `${id}.md`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(
      file,
      serializeMemory({
        id, type: "semantic", title: "Distilled", body: "b", project: "demo",
        machineId: "testmachine", scope: "portable", tags: ["reflection"],
        createdAt: "2026-06-01T00:00:00+00:00", updatedAt: "2026-06-01T00:00:00+00:00",
        provSource: "reflection", provModel: "deepseek/v4-flash", provSession: "",
        confidence: 0.6, supersedes: "",
      }),
      "utf-8",
    );

    await markReviewed(id);
    const reread = await readNote(id);
    expect(reread?.tags).toContain("reviewed");
    expect(reread?.provSource).toBe("reflection");
    expect(reread?.confidence).toBe(0.6);
  });

  it("is idempotent (no duplicate reviewed tag)", async () => {
    const created = await writeNote({ type: "semantic", title: "t", body: "b", tags: ["reviewed"] });
    await markReviewed(created.memory.id);
    const reread = await readNote(created.memory.id);
    expect(reread?.tags.filter((t) => t === "reviewed")).toHaveLength(1);
  });
});

describe("reflect (CLI runner)", () => {
  // Stub the CLI with a node script that echoes its args, so we test arg-building
  // and output capture without invoking Python. (tmpdir has no spaces on CI.)
  let echo: string;
  beforeEach(() => {
    echo = path.join(home, "echo.mjs");
    fs.writeFileSync(echo, "process.stdout.write(process.argv.slice(2).join(' '));\n");
    process.env.ANAMNESIS_CLI = `${process.execPath} ${echo}`;
  });

  it("builds dry-run args for all projects", async () => {
    const res = await reflect();
    expect(res.ok).toBe(true);
    expect(res.output).toBe("reflect");
  });

  it("scopes to a project", async () => {
    expect((await reflect({ project: "demo" })).output).toBe("reflect --project demo");
  });

  it("applies with --no-sync (dashboard reindexes, sync stays explicit)", async () => {
    expect((await reflect({ apply: true })).output).toBe("reflect --apply --no-sync");
  });

  it("captures failure output without throwing", async () => {
    const bad = path.join(home, "bad.mjs");
    fs.writeFileSync(bad, "process.stderr.write('boom'); process.exit(3);\n");
    process.env.ANAMNESIS_CLI = `${process.execPath} ${bad}`;
    const res = await reflect();
    expect(res.ok).toBe(false);
    expect(res.output).toContain("boom");
  });
});

describe("deleteNote", () => {
  it("removes a portable note's file and commits the removal", async () => {
    const created = await writeNote({ type: "semantic", title: "bye", body: "b", project: "p" });
    const file = path.join(mem, "semantic", `${created.memory.id}.md`);
    expect(fs.existsSync(file)).toBe(true);

    const res = await deleteNote(created.memory.id);
    expect(res.deleted).toBe(true);
    expect(res.commit).not.toBeNull();
    expect(fs.existsSync(file)).toBe(false);
    expect(await readNote(created.memory.id)).toBeNull();
  });

  it("throws for an unknown id", async () => {
    await expect(deleteNote("01KV000000000000000000000X")).rejects.toThrow(/not found/);
  });
});
