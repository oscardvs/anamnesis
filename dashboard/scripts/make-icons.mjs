import { mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

// Source of truth: assets/icon.svg is the full-bleed accent-gradient tile with
// the return-spiral already inside the maskable safe zone, so every PWA icon
// (including the maskable one) rasterizes straight from it.
const root = dirname(dirname(fileURLToPath(import.meta.url)));
const src = join(root, "assets", "icon.svg");
const out = join(root, "public", "icons");
await mkdir(out, { recursive: true });

const targets = [
  { name: "icon-192.png", size: 192 },
  { name: "icon-512.png", size: 512 },
  { name: "apple-touch-icon.png", size: 180 },
  { name: "maskable-512.png", size: 512 },
];
for (const t of targets) {
  await sharp(src).resize(t.size, t.size).png().toFile(join(out, t.name));
  console.log("wrote", t.name);
}

// Desktop app icon for electron-builder (build/ is git-ignored, so this is
// force-added). 1024px keeps it crisp on hi-dpi desktops.
const buildDir = join(root, "build");
await mkdir(buildDir, { recursive: true });
await sharp(src).resize(1024, 1024).png().toFile(join(buildDir, "icon.png"));
console.log("wrote build/icon.png");
