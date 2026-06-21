import { describe, expect, it } from "vitest";

import { computeLineDiff, diffStat } from "./diff";

describe("computeLineDiff", () => {
  it("marks adds, dels, and context with correct line numbers", () => {
    const lines = computeLineDiff("a\nb\nc\n", "a\nB\nc\n");
    expect(diffStat(lines)).toEqual({ additions: 1, deletions: 1 });
    const del = lines.find((l) => l.type === "del");
    const add = lines.find((l) => l.type === "add");
    expect(del?.oldNumber).toBe(2);
    expect(add?.newNumber).toBe(2);
    const context = lines.filter((l) => l.type === "context");
    expect(context.map((l) => l.content)).toEqual(["a", "c"]);
  });

  it("treats an empty old side as all additions (new file)", () => {
    const lines = computeLineDiff("", "x\ny\n");
    expect(diffStat(lines)).toEqual({ additions: 2, deletions: 0 });
  });

  it("reports no changes for identical text", () => {
    expect(diffStat(computeLineDiff("same\n", "same\n"))).toEqual({ additions: 0, deletions: 0 });
  });
});
