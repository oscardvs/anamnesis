import { NextResponse } from "next/server";

import { listMeta } from "@/lib/db";
import { buildGraph, type GraphNoteInput } from "@/lib/graph";
import { readNote } from "@/lib/store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** The memory graph for the 3D map: project hubs, member notes, and edges. */
export async function GET() {
  const metas = listMeta({ limit: 5000 });
  const notes: GraphNoteInput[] = await Promise.all(
    metas.map(async (m) => ({
      id: m.id,
      type: m.type,
      project: m.project,
      title: m.title,
      tags: m.tags,
      body: (await readNote(m.id))?.body ?? "",
    })),
  );
  return NextResponse.json(buildGraph(notes));
}
