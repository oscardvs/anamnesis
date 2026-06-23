// Build a temp ANAMNESIS_HOME with one real note and a Python-built index.db.
import { execFile } from "node:child_process";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import { notePath, serializeMemory } from "../src/lib/markdown";
import type { Memory } from "../src/lib/types";

const execFileAsync = promisify(execFile);
const dashboardDir = dirname(dirname(fileURLToPath(import.meta.url)));
const serverDir = join(dashboardDir, "..", "server");

export interface SeededStore {
  home: string;
  serverDir: string;
}

/** Create a temp store containing one note, indexed by the Python CLI. */
export async function seedStore(): Promise<SeededStore> {
  const home = await mkdtemp(join(tmpdir(), "anamnesis-e2e-"));
  const note: Memory = {
    id: "01J0SEED000000000000000000",
    type: "semantic",
    title: "Seed note for the standalone server test",
    body: "A seeded memory used to verify the headless server boots and reads the index.",
    project: "global",
    machineId: "e2e-machine",
    scope: "portable",
    tags: ["seed", "e2e"],
    createdAt: "2026-06-22T00:00:00+00:00",
    updatedAt: "2026-06-22T00:00:00+00:00",
    provSource: "human",
    provModel: "",
    provSession: "",
    confidence: 1.0,
    supersedes: "",
  };
  const rel = notePath(note.type, note.id);
  const file = join(home, "memory", rel);
  await mkdir(dirname(file), { recursive: true });
  await writeFile(file, serializeMemory(note), "utf8");

  // Build index.db from the markdown via the real Python reindexer.
  await execFileAsync("uv", ["run", "--project", serverDir, "anamnesis", "reindex"], {
    env: { ...process.env, ANAMNESIS_HOME: home },
  });

  return { home, serverDir };
}
