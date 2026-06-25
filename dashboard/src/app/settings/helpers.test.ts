import { describe, expect, it } from "vitest";

import { buildPatch, isOverridden, maskedKeyLabel, OVERRIDE_BADGE, type SettingsFormValues } from "./helpers";

const baseForm: SettingsFormValues = {
  machineId: "laptop",
  remote: "git@example:repo.git",
  provider: "deepseek",
  model: "deepseek-chat",
  baseUrl: "https://api.deepseek.com",
  timeout: "30",
  maxTokens: "1024",
  replacingKey: false,
  apiKey: "",
  clearKey: false,
};

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

describe("buildPatch", () => {
  it("omits a field whose dotted key is env-overridden", () => {
    const patch = buildPatch(baseForm, ["reflection.model"]);
    expect(patch).not.toHaveProperty("model");
    // The other fields are still present.
    expect(patch.provider).toBe("deepseek");
    expect(patch.machineId).toBe("laptop");
  });

  it("includes a non-overridden field", () => {
    const patch = buildPatch(baseForm, []);
    expect(patch.model).toBe("deepseek-chat");
    expect(patch.remote).toBe("git@example:repo.git");
    expect(patch.timeout).toBe("30");
    expect(patch.maxTokens).toBe("1024");
  });

  it("omits the api key when blank and not replacing", () => {
    const patch = buildPatch(baseForm, []);
    expect(patch).not.toHaveProperty("apiKey");
    expect(patch).not.toHaveProperty("clearApiKey");
  });

  it("sets the api key when replacing with a value", () => {
    const patch = buildPatch({ ...baseForm, replacingKey: true, apiKey: "sk-new" }, []);
    expect(patch.apiKey).toBe("sk-new");
    expect(patch).not.toHaveProperty("clearApiKey");
  });

  it("does not set the api key when replacing with a blank value", () => {
    const patch = buildPatch({ ...baseForm, replacingKey: true, apiKey: "" }, []);
    expect(patch).not.toHaveProperty("apiKey");
  });

  it("sets clearApiKey when the user chose clear", () => {
    const patch = buildPatch({ ...baseForm, clearKey: true }, []);
    expect(patch.clearApiKey).toBe(true);
    expect(patch).not.toHaveProperty("apiKey");
  });

  it("touches neither api-key field when reflection.api_key is env-overridden", () => {
    const patch = buildPatch(
      { ...baseForm, replacingKey: true, apiKey: "sk-new", clearKey: true },
      ["reflection.api_key"],
    );
    expect(patch).not.toHaveProperty("apiKey");
    expect(patch).not.toHaveProperty("clearApiKey");
  });
});
