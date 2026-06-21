/**
 * Front-matter codec: the exact markdown-file contract the Python store uses
 * (`_serialize` / `_deserialize` in `server/src/anamnesis/store.py`).
 *
 * A note file is `---\n<yaml>---\n<body>\n`. We parse with the permissive
 * core schema (so every scalar stays a string), and serialize with YAML 1.1
 * semantics + single quotes + unindented block sequences so the output matches
 * PyYAML's `safe_dump(sort_keys=False, allow_unicode=True)`. The 1.1 + quoting
 * matters: it keeps ISO timestamps quoted, so when Python re-reads the file with
 * `yaml.safe_load` it gets strings back, not coerced `datetime` objects.
 */
import YAML from "yaml";

import type { Memory, MemoryType, Scope } from "./types";

const FM_DELIM = "---\n";

function asString(value: unknown): string {
  if (value == null) return "";
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

/** Parse a note file (front-matter + body) into a Memory. */
export function parseMemory(text: string): Memory {
  if (!text.startsWith(FM_DELIM)) {
    throw new Error("memory file missing YAML front-matter");
  }
  const rest = text.slice(FM_DELIM.length);
  const end = rest.indexOf("\n" + FM_DELIM);
  if (end < 0) {
    throw new Error("memory file front-matter not terminated");
  }
  const frontStr = rest.slice(0, end);
  let body = rest.slice(end + ("\n" + FM_DELIM).length);
  if (body.endsWith("\n")) body = body.slice(0, -1); // drop the single trailing newline

  const meta = (YAML.parse(frontStr) ?? {}) as Record<string, unknown>;
  const rawTags = meta.tags;
  return {
    id: asString(meta.id),
    type: asString(meta.type) as MemoryType,
    title: asString(meta.title),
    body,
    project: meta.project != null ? asString(meta.project) : "global",
    machineId: meta.machine_id != null ? asString(meta.machine_id) : "unknown",
    scope: (meta.scope != null ? asString(meta.scope) : "portable") as Scope,
    tags: Array.isArray(rawTags) ? rawTags.map(asString) : [],
    createdAt: asString(meta.created_at),
    updatedAt: asString(meta.updated_at),
  };
}

/**
 * Render a Memory as a note file, byte-compatible with the Python store's
 * `_serialize` (same key order, single quotes, unindented tag sequence).
 */
export function serializeMemory(mem: Memory): string {
  const front = {
    id: mem.id,
    type: mem.type,
    title: mem.title,
    project: mem.project,
    machine_id: mem.machineId,
    scope: mem.scope,
    created_at: mem.createdAt,
    updated_at: mem.updatedAt,
    tags: mem.tags,
  };
  const yamlStr = YAML.stringify(front, {
    version: "1.1",
    singleQuote: true,
    indentSeq: false,
    lineWidth: 0,
  });
  return `${FM_DELIM}${yamlStr}${FM_DELIM}${mem.body}\n`;
}

/** The markdown file path (relative to `memory/`) for a note. */
export function notePath(type: MemoryType, id: string): string {
  return `${type}/${id}.md`;
}
