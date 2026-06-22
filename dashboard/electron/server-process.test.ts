import { createServer } from "node:net";

import { afterEach, describe, expect, it } from "vitest";

import { buildServerEnv, getFreePort, waitForPort } from "./server-process";

describe("getFreePort", () => {
  it("returns a usable, bindable port", async () => {
    const port = await getFreePort();
    expect(port).toBeGreaterThan(0);
    await new Promise<void>((resolve, reject) => {
      const s = createServer().listen(port, "127.0.0.1");
      s.on("listening", () => s.close(() => resolve()));
      s.on("error", reject);
    });
  });
});

describe("waitForPort", () => {
  let server: ReturnType<typeof createServer> | undefined;
  afterEach(() => server?.close());

  it("resolves once a listener accepts connections", async () => {
    const port = await getFreePort();
    server = createServer().listen(port, "127.0.0.1");
    await expect(waitForPort(port, 5000)).resolves.toBeUndefined();
  });

  it("rejects when nothing comes up before the timeout", async () => {
    const port = await getFreePort();
    await expect(waitForPort(port, 300)).rejects.toThrow();
  });
});

describe("buildServerEnv", () => {
  it("augments PATH with ~/.local/bin and preserves ANAMNESIS_* and PORT", () => {
    const env = buildServerEnv({
      PATH: "/usr/bin",
      ANAMNESIS_HOME: "/tmp/store",
      PORT: "1234",
    });
    expect(env.PATH).toContain("/usr/bin");
    expect(env.PATH).toContain(".local/bin");
    expect(env.ANAMNESIS_HOME).toBe("/tmp/store");
    expect(env.PORT).toBe("1234");
  });
});
