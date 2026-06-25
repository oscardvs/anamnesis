/**
 * Invoke the `anamnesis` CLI from the dashboard. Python stays the single owner
 * of the store and its config contract; the dashboard shells out and parses the
 * CLI output, never touching the underlying files directly.
 *
 * The default `--project ../server` is a literal relative arg resolved by uv
 * against the run cwd (the dashboard dir under `next dev`/`start`); we avoid
 * computing it with process.cwd()/path.* so the bundler's file tracer does not
 * walk up into the parent project tree.
 */
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { resolveHome, resolveMachineId } from "./config";

const execFileAsync = promisify(execFile);
const MAX_BUFFER = 64 * 1024 * 1024;

/** Resolve how to invoke the `anamnesis` CLI (overridable for non-default setups). */
export function cliInvocation(): { cmd: string; prefix: string[] } {
  const override = process.env.ANAMNESIS_CLI;
  if (override) {
    const parts = override.split(/\s+/).filter(Boolean);
    return { cmd: parts[0], prefix: parts.slice(1) };
  }
  const uv = process.env.ANAMNESIS_UV || "uv";
  const serverDir = process.env.ANAMNESIS_SERVER || "../server";
  return { cmd: uv, prefix: ["run", "--project", serverDir, "anamnesis"] };
}

/** Run the `anamnesis` CLI with the store env pinned, returning stdout/stderr. */
export async function runCli(args: string[]): Promise<{ stdout: string; stderr: string }> {
  const { cmd, prefix } = cliInvocation();
  const env = {
    ...process.env,
    ANAMNESIS_HOME: resolveHome(),
    ANAMNESIS_MACHINE_ID: resolveMachineId(),
  };
  const { stdout, stderr } = await execFileAsync(cmd, [...prefix, ...args], {
    env,
    maxBuffer: MAX_BUFFER,
  });
  return { stdout, stderr };
}
