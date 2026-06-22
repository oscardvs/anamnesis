// electron-rebuild built better-sqlite3 for Electron's ABI into the project
// node_modules. The packaged app contains Node-ABI copies (Next file-traced one
// under .next/standalone, and the root one). Overwrite every packaged
// better_sqlite3.node with the Electron-ABI build so the Electron-hosted server
// loads a matching binary. We search recursively rather than guess fixed paths,
// since the unpacked layout differs across platforms.
const { copyFile, readdir } = require("node:fs/promises");
const { join } = require("node:path");

const NODE_FILE = "better_sqlite3.node";

async function findFiles(dir, name, acc) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return acc;
  }
  for (const entry of entries) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) await findFiles(p, name, acc);
    else if (entry.name === name) acc.push(p);
  }
  return acc;
}

exports.default = async function afterPack(context) {
  const { appOutDir, packager } = context;
  const src = join(
    packager.projectDir,
    "node_modules",
    "better-sqlite3",
    "build",
    "Release",
    NODE_FILE,
  );

  const found = await findFiles(appOutDir, NODE_FILE, []);
  if (found.length === 0) {
    console.warn(
      `afterPack: WARNING no ${NODE_FILE} found under ${appOutDir}; the packaged app may fail to open the index.`,
    );
    return;
  }
  for (const dest of found) {
    await copyFile(src, dest);
    console.log("afterPack: synced electron-ABI better_sqlite3.node ->", dest);
  }
};
