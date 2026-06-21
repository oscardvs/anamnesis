import { NextResponse } from "next/server";

import { noteDiff } from "@/lib/history";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * GET /api/notes/:id/diff?from=<ref|empty>&to=<ref|working>
 * Diff a note between two revisions (or against the working tree).
 */
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { searchParams } = new URL(request.url);
  const from = searchParams.get("from") ?? "empty";
  const to = searchParams.get("to") ?? "working";
  const diff = await noteDiff(id, from, to);
  if (!diff) {
    return NextResponse.json({ error: "note not found" }, { status: 404 });
  }
  return NextResponse.json({ diff, from, to });
}
