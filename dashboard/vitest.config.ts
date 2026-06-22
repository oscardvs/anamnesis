import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // The standalone build copies src/ (including *.test.ts) into
    // .next/standalone, so exclude build output to avoid running duplicates.
    // e2e/ holds the heavy standalone boot test, run via `npm run test:e2e`.
    exclude: [...configDefaults.exclude, ".next/**", "e2e/**"],
  },
});
