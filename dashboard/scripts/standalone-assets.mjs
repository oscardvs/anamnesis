// Copy public/ and .next/static/ into .next/standalone/ so the standalone
// server can serve them. Cross-platform (no shell cp). No-op if no standalone
// build is present (e.g. after a plain `next build` without output:standalone).
import { cp, access } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const standalone = join(root, ".next", "standalone");

async function exists(p) {
  try {
    await access(p);
    return true;
  } catch {
    return false;
  }
}

if (!(await exists(join(standalone, "server.js")))) {
  console.log("standalone-assets: no standalone build, skipping");
  process.exit(0);
}

await cp(join(root, "public"), join(standalone, "public"), { recursive: true });
await cp(join(root, ".next", "static"), join(standalone, ".next", "static"), {
  recursive: true,
});
console.log("standalone-assets: copied public/ and .next/static/");
