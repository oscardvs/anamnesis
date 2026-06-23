import { describe, expect, it } from "vitest";

import { provenanceBadge } from "./provenance";

describe("provenanceBadge", () => {
  it("returns null for human notes (quiet by default)", () => {
    expect(provenanceBadge("human", 1)).toBeNull();
  });

  it("labels a reflection note with its confidence score, in the warn tone", () => {
    expect(provenanceBadge("reflection", 0.6)).toEqual({ label: "reflection · 0.6", tone: "warn" });
  });

  it("shows session-end as a muted info chip with no score at confidence 1.0", () => {
    expect(provenanceBadge("session-end", 1)).toEqual({ label: "session", tone: "info" });
  });

  it("shows import as a neutral chip", () => {
    expect(provenanceBadge("import", 1)).toEqual({ label: "import", tone: "neutral" });
  });

  it("appends the score only when confidence is below 1.0", () => {
    expect(provenanceBadge("session-end", 0.8)).toEqual({ label: "session · 0.8", tone: "info" });
  });
});
