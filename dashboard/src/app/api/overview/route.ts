import { NextResponse } from "next/server";

import { indexExists, stats } from "@/lib/db";
import { repoState } from "@/lib/git";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/overview - index stats, repo/sync state, and whether the index exists. */
export async function GET() {
  const repo = await repoState();
  return NextResponse.json({ stats: stats(), repo, indexExists: indexExists() });
}
