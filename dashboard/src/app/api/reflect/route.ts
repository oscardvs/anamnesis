import { NextResponse } from "next/server";

import { reflect } from "@/lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** POST /api/reflect?project=&apply=1 - dry-run by default; apply writes + reindexes. */
export async function POST(request: Request) {
  const { searchParams } = new URL(request.url);
  const project = searchParams.get("project") || undefined;
  const apply = searchParams.get("apply") === "1";
  const result = await reflect({ project, apply });
  return NextResponse.json(result, { status: result.ok ? 200 : 500 });
}
