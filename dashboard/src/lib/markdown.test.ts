import { describe, expect, it } from "vitest";

import { parseMemory, serializeMemory } from "./markdown";
import type { Memory } from "./types";

const sample: Memory = {
  id: "01KV2V3G79X1VNYD9WC0Z83WDW",
  type: "semantic",
  title: "BrokerMind AI: target architecture",
  body: "Line one\n\nLine two with **bold**.",
  project: "github.com/oscardvs/flawy",
  machineId: "odesha",
  scope: "portable",
  tags: ["import", "kind:unknown"],
  createdAt: "2026-06-14T10:33:41+00:00",
  updatedAt: "2026-06-14T10:33:41+00:00",
};

describe("markdown front-matter codec", () => {
  it("round-trips a memory exactly", () => {
    expect(parseMemory(serializeMemory(sample))).toEqual(sample);
  });

  it("single-quotes ISO timestamps so Python reads them as strings, not datetimes", () => {
    const text = serializeMemory(sample);
    expect(text).toContain("created_at: '2026-06-14T10:33:41+00:00'");
    expect(text).toContain("updated_at: '2026-06-14T10:33:41+00:00'");
  });

  it("emits an unindented tag block sequence (PyYAML style)", () => {
    expect(serializeMemory(sample)).toContain("tags:\n- import\n- kind:unknown\n");
  });

  it("ends the file with exactly one trailing newline", () => {
    const text = serializeMemory(sample);
    expect(text.endsWith("\n")).toBe(true);
    expect(text.endsWith("\n\n")).toBe(false);
  });

  it("preserves key order matching the Python store", () => {
    const text = serializeMemory(sample);
    const keys = text
      .split("---\n")[1]
      .split("\n")
      .filter((l) => /^\w/.test(l))
      .map((l) => l.split(":")[0]);
    expect(keys).toEqual([
      "id",
      "type",
      "title",
      "project",
      "machine_id",
      "scope",
      "created_at",
      "updated_at",
      "tags",
    ]);
  });

  it("defaults optional fields when absent", () => {
    const text =
      "---\nid: x\ntype: episodic\ntitle: t\n" +
      "created_at: '2026-01-01T00:00:00+00:00'\nupdated_at: '2026-01-01T00:00:00+00:00'\n" +
      "tags: []\n---\nbody\n";
    const m = parseMemory(text);
    expect(m.project).toBe("global");
    expect(m.machineId).toBe("unknown");
    expect(m.scope).toBe("portable");
    expect(m.tags).toEqual([]);
    expect(m.body).toBe("body");
  });

  it("throws on a file with no front-matter", () => {
    expect(() => parseMemory("no front matter here")).toThrow();
  });
});
