import { NextResponse } from "next/server";

import { backfillProvenance } from "@/lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** POST /api/backfill-provenance?apply=1 - dry-run by default; apply rewrites + reindexes. */
export async function POST(request: Request) {
  const { searchParams } = new URL(request.url);
  const apply = searchParams.get("apply") === "1";
  const result = await backfillProvenance({ apply });
  return NextResponse.json(result, { status: result.ok ? 200 : 500 });
}
