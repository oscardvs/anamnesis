import { NextResponse } from "next/server";

import { countsByMachine } from "@/lib/db";
import { fleet, repoState } from "@/lib/git";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/fleet - machines (last-sync, counts) plus repo/sync state. */
export async function GET() {
  const [machines, repo] = await Promise.all([fleet(countsByMachine()), repoState()]);
  return NextResponse.json({ machines, repo });
}
