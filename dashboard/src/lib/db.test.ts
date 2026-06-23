import Database from "better-sqlite3";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { closeDb, countPendingReflections, listMeta } from "./db";

// Build a minimal index.db (the columns the dashboard reads) and point the store
// at it. Mirrors the relevant subset of server/src/anamnesis/store.py _SCHEMA.
let home: string;
const saved: Record<string, string | undefined> = {};

const SCHEMA = `
CREATE TABLE memories (
  id TEXT PRIMARY KEY, type TEXT, title TEXT, body_path TEXT, project TEXT,
  machine_id TEXT, scope TEXT, created_at TEXT, updated_at TEXT,
  prov_source TEXT NOT NULL DEFAULT 'human', prov_model TEXT, prov_session TEXT,
  confidence REAL NOT NULL DEFAULT 1.0, supersedes TEXT
);
CREATE TABLE memory_tags (memory_id TEXT, tag TEXT, PRIMARY KEY (memory_id, tag));
`;

function insert(db: Database.Database, m: Record<string, unknown>, tags: string[]) {
  db.prepare(
    "INSERT INTO memories (id,type,title,body_path,project,machine_id,scope,created_at,updated_at,prov_source,prov_model,prov_session,confidence,supersedes)" +
      " VALUES (@id,@type,@title,@body_path,@project,@machine_id,@scope,@created_at,@updated_at,@prov_source,@prov_model,@prov_session,@confidence,@supersedes)",
  ).run({
    type: "semantic", title: "t", body_path: `semantic/${m.id}.md`, project: "demo",
    machine_id: "m", scope: "portable", created_at: "2026-01-01T00:00:00+00:00",
    updated_at: "2026-01-01T00:00:00+00:00", prov_model: "", prov_session: "",
    confidence: 1.0, supersedes: "", ...m,
  });
  for (const tag of tags) db.prepare("INSERT INTO memory_tags VALUES (?,?)").run(m.id, tag);
}

beforeEach(() => {
  home = fs.mkdtempSync(path.join(os.tmpdir(), "anamnesis-db-"));
  const db = new Database(path.join(home, "index.db"));
  db.exec(SCHEMA);
  insert(db, { id: "00000000000000000000000001", prov_source: "human", confidence: 1.0 }, []);
  insert(db, { id: "00000000000000000000000002", prov_source: "reflection", confidence: 0.6 }, ["reflection"]);
  insert(db, { id: "00000000000000000000000003", prov_source: "reflection", confidence: 0.6 }, ["reflection", "reviewed"]);
  db.close();
  saved.home = process.env.ANAMNESIS_HOME;
  process.env.ANAMNESIS_HOME = home;
  closeDb();
});

afterEach(() => {
  fs.rmSync(home, { recursive: true, force: true });
  if (saved.home === undefined) delete process.env.ANAMNESIS_HOME;
  else process.env.ANAMNESIS_HOME = saved.home;
  closeDb();
});

describe("db provenance reads", () => {
  it("returns provenance fields on metadata rows", () => {
    const all = listMeta({ limit: 100 });
    const human = all.find((m) => m.id === "00000000000000000000000001");
    expect(human?.provSource).toBe("human");
    expect(human?.confidence).toBe(1.0);
  });

  it("filters by provSource", () => {
    const refl = listMeta({ provSource: "reflection", limit: 100 });
    expect(refl.map((m) => m.id).sort()).toEqual([
      "00000000000000000000000002",
      "00000000000000000000000003",
    ]);
  });

  it("excludes a tag (pending = reflection minus reviewed)", () => {
    const pending = listMeta({ provSource: "reflection", excludeTag: "reviewed", limit: 100 });
    expect(pending.map((m) => m.id)).toEqual(["00000000000000000000000002"]);
  });

  it("counts pending reflections", () => {
    expect(countPendingReflections()).toBe(1);
  });
});
