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
  { name: "apple-touch-icon.png", size: 180 },
];
for (const t of targets) {
  await sharp(src).resize(t.size, t.size).png().toFile(join(out, t.name));
  console.log("wrote", t.name);
}

// Maskable: keep the glyph inside the safe zone (~62% of the canvas) on a solid
// background so Android's circular/squircle mask does not clip it.
const size = 512;
const inner = Math.round(size * 0.625);
const glyph = await sharp(src).resize(inner, inner).png().toBuffer();
await sharp({
  create: { width: size, height: size, channels: 4, background: "#0b0b0c" },
})
  .composite([{ input: glyph, gravity: "center" }])
  .png()
  .toFile(join(out, "maskable-512.png"));
console.log("wrote", "maskable-512.png");
