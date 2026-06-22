import { spawn, type ChildProcess } from "node:child_process";
import { rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { connect } from "node:net";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { seedStore, type SeededStore } from "./seed";

const dashboardDir = dirname(dirname(fileURLToPath(import.meta.url)));
const serverJs = join(dashboardDir, ".next", "standalone", "server.js");
const PORT = 39517;

function waitForPort(port: number, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const tryOnce = () => {
      const sock = connect(port, "127.0.0.1");
      sock.once("connect", () => {
        sock.destroy();
        resolve();
      });
      sock.once("error", () => {
        sock.destroy();
        if (Date.now() > deadline) reject(new Error(`port ${port} not up in ${timeoutMs}ms`));
        else setTimeout(tryOnce, 150);
      });
    };
    tryOnce();
  });
}

const hasBuild = existsSync(serverJs);
describe.skipIf(!hasBuild)("standalone server (requires `npm run build` first)", () => {
  let store: SeededStore;
  let proc: ChildProcess;

  beforeAll(async () => {
    store = await seedStore();
    proc = spawn(process.execPath, [serverJs], {
      cwd: dashboardDir,
      env: {
        ...process.env,
        PORT: String(PORT),
        HOSTNAME: "127.0.0.1",
        ANAMNESIS_HOME: store.home,
        ANAMNESIS_SERVER: store.serverDir,
      },
      stdio: "inherit",
    });
    await waitForPort(PORT, 30_000);
  });

  afterAll(async () => {
    proc?.kill("SIGTERM");
    if (store?.home) await rm(store.home, { recursive: true, force: true });
  });

  it("serves /api/overview with the seeded index (exercises the native binary)", async () => {
    const res = await fetch(`http://127.0.0.1:${PORT}/api/overview`);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.indexExists).toBe(true);
    expect(body.stats.total).toBeGreaterThanOrEqual(1);
  });

  it("serves the rendered home page", async () => {
    const res = await fetch(`http://127.0.0.1:${PORT}/`);
    expect(res.status).toBe(200);
    expect(await res.text()).toContain("Anamnesis");
  });
});
