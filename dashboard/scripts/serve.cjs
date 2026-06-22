// Canonical entry for the standalone server. Bind loopback by default unless
// HOSTNAME is explicitly overridden, then start the Next standalone server.
// Exposure is meant to be only via `tailscale serve` (tailnet-only), never
// 0.0.0.0. This makes the loopback binding an invariant of this entry point
// rather than relying on every caller to set HOSTNAME.
process.env.HOSTNAME ||= "127.0.0.1";
require("../.next/standalone/server.js");
