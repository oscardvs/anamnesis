import { spawn, type ChildProcess } from "node:child_process";
import { join } from "node:path";

import { app, BrowserWindow } from "electron";

import { buildServerEnv, getFreePort, waitForPort } from "./server-process";

// With asar disabled, packaged files live under resources/app, so the
// dist-electron -> app-root relationship is the same as in dev: one level up
// from __dirname. (process.resourcesPath would point at resources/, missing app/.)
const appRoot = join(__dirname, "..");
const serverJs = join(appRoot, ".next", "standalone", "server.js");

let serverProc: ChildProcess | undefined;

async function startServer(): Promise<number> {
  const port = await getFreePort();
  serverProc = spawn(process.execPath, [serverJs], {
    cwd: appRoot,
    env: buildServerEnv({
      ...process.env,
      // Run the Electron binary in pure-Node mode to host the Next server.
      ELECTRON_RUN_AS_NODE: "1",
      PORT: String(port),
      HOSTNAME: "127.0.0.1",
    }),
    stdio: "inherit",
  });
  serverProc.on("exit", (code) => {
    if (!app.isPackaged) console.error("anamnesis server exited", code);
    if (BrowserWindow.getAllWindows().length === 0) app.quit();
  });
  await waitForPort(port, 30_000);
  return port;
}

async function createWindow(): Promise<void> {
  const port = await startServer();
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    webPreferences: { contextIsolation: true, preload: join(__dirname, "preload.js") },
  });
  await win.loadURL(`http://127.0.0.1:${port}`);
}

app.whenReady()
  .then(createWindow)
  .catch((err) => {
    // If the server never came up (e.g. waitForPort timed out), do not leave a
    // windowless app hanging: log and quit so the child is killed on before-quit.
    console.error("anamnesis: failed to start the server", err);
    app.quit();
  });

app.on("window-all-closed", () => app.quit());

app.on("before-quit", () => {
  serverProc?.kill("SIGTERM");
});
