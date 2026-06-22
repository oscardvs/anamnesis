// Bundle the Electron main + preload (TypeScript) to CommonJS in dist-electron/.
import { build } from "esbuild";

const common = {
  bundle: true,
  platform: "node",
  format: "cjs",
  target: "node20",
  external: ["electron"],
  sourcemap: true,
};

await build({ ...common, entryPoints: ["electron/main.ts"], outfile: "dist-electron/main.js" });
await build({
  ...common,
  entryPoints: ["electron/preload.ts"],
  outfile: "dist-electron/preload.js",
});
console.log("build-electron: wrote dist-electron/");
