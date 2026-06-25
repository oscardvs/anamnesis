import { describe, expect, it, vi } from "vitest";

vi.mock("./cli", () => ({
  runCli: vi.fn(),
}));

import { runCli } from "./cli";
import { getSettings } from "./settings";

describe("getSettings", () => {
  it("parses config list --json and never exposes a raw key", async () => {
    const payload = {
      machine_id: { value: "odesha", source: "file" },
      remote: { value: "/x.git", source: "file" },
      reflection: {
        provider: { value: "deepseek", source: "file" },
        model: { value: "deepseek-v4-flash", source: "env" },
        base_url: { value: "https://api.deepseek.com", source: "file" },
        timeout: { value: 30, source: "default" },
        max_tokens: { value: 120000, source: "default" },
        api_key_set: true,
        api_key_preview: "sk-...ef",
        api_key_source: "file",
      },
    };
    (runCli as ReturnType<typeof vi.fn>).mockResolvedValue({
      stdout: JSON.stringify(payload),
      stderr: "",
    });
    const s = await getSettings();
    expect(s.reflection.provider).toBe("deepseek");
    expect(s.reflection.apiKeySet).toBe(true);
    expect(s.reflection.apiKeyPreview).toBe("sk-...ef");
    expect(s.envOverrides).toContain("reflection.model");
    expect(JSON.stringify(s)).not.toContain("undefined");
  });
});
