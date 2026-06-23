import { NextResponse } from "next/server";

import { markReviewed } from "@/lib/store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** POST /api/notes/:id/keep - mark a reflection note reviewed (adds the `reviewed` tag). */
export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try {
    return NextResponse.json(await markReviewed(id));
  } catch (err) {
    return NextResponse.json({ error: (err as Error).message }, { status: 500 });
  }
}
