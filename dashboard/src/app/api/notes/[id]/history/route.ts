import { NextResponse } from "next/server";

import { noteHistory } from "@/lib/git";
import { noteRelPath } from "@/lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/notes/:id/history - commit history for a single note (follows renames). */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const rel = noteRelPath(id);
  if (!rel) {
    return NextResponse.json({ error: "note not found" }, { status: 404 });
  }
  const commits = await noteHistory(rel);
  return NextResponse.json({ commits });
}
