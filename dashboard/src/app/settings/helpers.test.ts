import { describe, expect, it } from "vitest";

import { isOverridden, maskedKeyLabel, OVERRIDE_BADGE } from "./helpers";

describe("isOverridden", () => {
  it("is true when the dotted key is in envOverrides", () => {
    expect(isOverridden(["reflection.model", "remote"], "reflection.model")).toBe(true);
    expect(isOverridden(["reflection.model"], "remote")).toBe(false);
  });

  it("is false for an empty override list", () => {
    expect(isOverridden([], "reflection.model")).toBe(false);
  });
});

describe("maskedKeyLabel", () => {
  it("prefers a non-empty preview", () => {
    expect(maskedKeyLabel({ apiKeySet: true, apiKeyPreview: "sk-...ef" })).toBe("sk-...ef");
  });

  it("falls back to a generic label when set but no preview", () => {
    expect(maskedKeyLabel({ apiKeySet: true, apiKeyPreview: "" })).toBe("set");
  });

  it("reports an unset key", () => {
    expect(maskedKeyLabel({ apiKeySet: false, apiKeyPreview: "" })).toBe("not set");
  });
});

describe("OVERRIDE_BADGE", () => {
  it("explains that the environment wins", () => {
    expect(OVERRIDE_BADGE).toMatch(/environment/i);
  });
});
