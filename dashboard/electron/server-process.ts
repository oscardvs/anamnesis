// Helpers for running the standalone Next server under Electron. Electron-free
// (pure node) so they are unit-testable without launching a window.
import { connect, createServer } from "node:net";
import { homedir } from "node:os";
import { delimiter, join } from "node:path";

/** Ask the OS for an available ephemeral port. */
export function getFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = createServer();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const addr = srv.address();
      if (addr && typeof addr === "object") {
        const { port } = addr;
        srv.close(() => resolve(port));
      } else {
        srv.close(() => reject(new Error("could not get a free port")));
      }
    });
  });
}

/** Resolve once 127.0.0.1:port accepts a connection, or reject on timeout. */
export function waitForPort(port: number, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const sock = connect(port, "127.0.0.1");
      sock.once("connect", () => {
        sock.destroy();
        resolve();
      });
      sock.once("error", () => {
        sock.destroy();
        if (Date.now() > deadline) reject(new Error(`server not up on port ${port}`));
        else setTimeout(attempt, 150);
      });
    };
    attempt();
  });
}

/**
 * Build the child env for the spawned server. A GUI-launched app inherits a
 * stripped PATH, so add the common locations where uv and git live; preserve
 * everything else (including ANAMNESIS_* and PORT).
 */
export function buildServerEnv(base: NodeJS.ProcessEnv): NodeJS.ProcessEnv {
  const home = homedir();
  const extra = [
    join(home, ".local", "bin"),
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    join(home, ".nvm", "current", "bin"),
  ];
  const existing = base.PATH ? base.PATH.split(delimiter) : [];
  const merged = [...new Set([...existing, ...extra])].filter(Boolean);
  return { ...base, PATH: merged.join(delimiter) };
}
