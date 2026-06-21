import { NextResponse } from "next/server";

import { commitDetail } from "@/lib/history";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/commits/:hash - the per-file diffs a commit introduced. */
export async function GET(_request: Request, { params }: { params: Promise<{ hash: string }> }) {
  const { hash } = await params;
  const files = await commitDetail(hash);
  return NextResponse.json({ hash, files });
}
