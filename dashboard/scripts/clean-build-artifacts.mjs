// Remove desktop build artifacts before a build. Next's standalone trace copies
// the project tree into .next/standalone; if dist/ (a prior AppImage/deb) is
// present it gets copied in too, ballooning the bundle on each rebuild. Running
// this as a prebuild step keeps every build path (web, hub, desktop) lean.
import { rmSync } from "node:fs";

for (const dir of ["dist", "dist-electron"]) {
  rmSync(dir, { recursive: true, force: true });
}
