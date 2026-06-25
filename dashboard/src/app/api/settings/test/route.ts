import { NextResponse } from "next/server";

import { runCli } from "@/lib/cli";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** POST /api/settings/test - ping the reflection provider via `anamnesis config test`. */
export async function POST() {
  try {
    const { stdout, stderr } = await runCli(["config", "test"]);
    const message = (stdout + stderr).trim();
    return NextResponse.json({ ok: !/fail|failed|incomplete/i.test(message), message });
  } catch (err) {
    const e = err as { stdout?: string; stderr?: string; message?: string };
    return NextResponse.json({
      ok: false,
      message: ((e.stdout || "") + (e.stderr || "") || e.message || "test failed").trim(),
    });
  }
}
