import { NextResponse } from "next/server";

import { globalHistory } from "@/lib/git";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/history?limit= - the global commit history of the memory repo. */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = Number(searchParams.get("limit") ?? "") || 200;
  const commits = await globalHistory(limit);
  return NextResponse.json({ commits });
}
