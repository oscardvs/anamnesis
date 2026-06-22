// Build the desktop package, then ALWAYS restore the Node-ABI better-sqlite3.
// electron-rebuild rebuilds better-sqlite3 for Electron's ABI, which breaks the
// web flow (npm run dev/start/test) until it is rebuilt for Node. Running the
// restore in a finally means a failed package step does not leave the working
// tree on the Electron ABI.
import { execSync } from "node:child_process";

const run = (cmd) => execSync(cmd, { stdio: "inherit" });

let failed = false;
try {
  // `npm run build` runs the prebuild clean (scripts/clean-build-artifacts.mjs),
  // so a prior dist/ artifact is not traced into the new standalone bundle.
  run("npm run build");
  run("npm run build:electron");
  run("npx electron-rebuild -f -w better-sqlite3");
  run("npx electron-builder");
} catch {
  failed = true;
} finally {
  try {
    run("npm rebuild better-sqlite3");
  } catch {
    console.error(
      "desktop-build: WARNING could not restore the Node-ABI better-sqlite3; run `npm rebuild better-sqlite3` before using the web flow.",
    );
  }
}

process.exit(failed ? 1 : 0);
