// Ensure every packaged better-sqlite3 copy has the Electron-ABI native binary.
//
// electron-rebuild rebuilds better-sqlite3 for Electron's ABI in the ROOT
// node_modules, but electron-builder strips the build/ dir from the NESTED copy
// that Next traced into .next/standalone (leaving package.json + lib/ but no
// .node). The standalone server requires that nested copy, so without its .node
// it throws (Node does not walk up once it has found the package).
//
// We find every better-sqlite3 package dir in the output and place the
// Electron-ABI .node at build/Release/better_sqlite3.node, creating the dir if
// electron-builder dropped it. electron-rebuild has already produced that
// binary in the project's root node_modules by the time afterPack runs.
const { copyFile, readdir, mkdir } = require("node:fs/promises");
const { join, dirname } = require("node:path");

async function findPackageDirs(dir, name, acc) {
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return acc;
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const p = join(dir, entry.name);
    if (entry.name === name) acc.push(p);
    else await findPackageDirs(p, name, acc);
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
    "better_sqlite3.node",
  );

  const dirs = await findPackageDirs(appOutDir, "better-sqlite3", []);
  if (dirs.length === 0) {
    console.warn(
      `afterPack: WARNING no better-sqlite3 dir found under ${appOutDir}; the packaged app may fail to open the index.`,
    );
    return;
  }
  for (const dir of dirs) {
    const dest = join(dir, "build", "Release", "better_sqlite3.node");
    await mkdir(dirname(dest), { recursive: true });
    await copyFile(src, dest);
    console.log("afterPack: placed electron-ABI better_sqlite3.node ->", dest);
  }
};
