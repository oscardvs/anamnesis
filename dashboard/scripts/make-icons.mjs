import { mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const src = join(root, "assets", "icon.svg");
const out = join(root, "public", "icons");
await mkdir(out, { recursive: true });

const targets = [
  { name: "icon-192.png", size: 192 },
  { name: "icon-512.png", size: 512 },
  { name: "maskable-512.png", size: 512 },
  { name: "apple-touch-icon.png", size: 180 },
];
for (const t of targets) {
  await sharp(src).resize(t.size, t.size).png().toFile(join(out, t.name));
  console.log("wrote", t.name);
}
