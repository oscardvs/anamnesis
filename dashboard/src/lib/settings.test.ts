import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./cli", () => ({
  runCli: vi.fn(),
}));

import { runCli } from "./cli";
import { getSettings, setSettings } from "./settings";

const mockCli = runCli as ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockCli.mockReset();
  mockCli.mockResolvedValue({ stdout: "", stderr: "" });
});

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
    mockCli.mockResolvedValue({
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

describe("setSettings", () => {
  it("leaves a blank apiKey unchanged (never shells it to the CLI)", async () => {
    await setSettings({ model: "deepseek-v4-flash", apiKey: "" });
    expect(mockCli).toHaveBeenCalledTimes(1);
    const args = mockCli.mock.calls[0][0] as string[];
    expect(args).toEqual(["config", "set", "reflection.model", "deepseek-v4-flash"]);
    expect(args).not.toContain("reflection.api_key");
  });

  it("clears the stored key via config unset reflection.api_key", async () => {
    await setSettings({ clearApiKey: true });
    expect(mockCli).toHaveBeenCalledTimes(1);
    expect(mockCli).toHaveBeenCalledWith(["config", "unset", "reflection.api_key"]);
  });
});
