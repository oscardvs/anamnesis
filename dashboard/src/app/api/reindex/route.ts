import { NextResponse } from "next/server";

import { reindex } from "@/lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** POST /api/reindex - rebuild the SQLite index from markdown via the Python CLI. */
export async function POST() {
  const reindexed = await reindex();
  return NextResponse.json({ reindexed }, { status: reindexed ? 200 : 500 });
}
