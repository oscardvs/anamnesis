import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Self-contained server output (server.js + traced node_modules) for the
  // systemd/tailnet PWA and the Electron desktop shell.
  output: "standalone",
  // Pin the workspace root to this folder so a stray ~/package-lock.json does
  // not trigger Next's multi-lockfile root inference warning.
  turbopack: { root: __dirname },
  // better-sqlite3 is a native module; keep it external to the server bundle.
  serverExternalPackages: ["better-sqlite3"],
};

export default nextConfig;
