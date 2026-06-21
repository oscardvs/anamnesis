import { NextResponse } from "next/server";

import { sync } from "@/lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** POST /api/sync - run one git sync cycle (commit/pull/push), surfacing conflicts. */
export async function POST() {
  const outcome = await sync();
  return NextResponse.json(outcome, { status: outcome.conflicted ? 409 : 200 });
}
