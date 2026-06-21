import { NextResponse } from "next/server";

import { listMeta, searchMeta } from "@/lib/db";
import { writeNote, type WriteInput } from "@/lib/store";
import { MEMORY_TYPES, type MemoryType } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/notes?q=&project=&type=&limit= - search (when q present) or list. */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const q = searchParams.get("q")?.trim() ?? "";
  const project = searchParams.get("project") ?? undefined;
  const typeParam = searchParams.get("type");
  const type = MEMORY_TYPES.includes(typeParam as MemoryType)
    ? (typeParam as MemoryType)
    : undefined;
  const limit = Number(searchParams.get("limit") ?? "") || undefined;

  const notes = q
    ? searchMeta(q, { project, type, limit })
    : listMeta({ project, type, limit });
  return NextResponse.json({ notes, query: q });
}

/** POST /api/notes - create a note, commit it locally, and reindex. */
export async function POST(request: Request) {
  let body: Partial<WriteInput>;
  try {
    body = (await request.json()) as Partial<WriteInput>;
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  if (!body.type || !MEMORY_TYPES.includes(body.type)) {
    return NextResponse.json({ error: "type must be one of " + MEMORY_TYPES.join(", ") }, { status: 400 });
  }
  if (!body.title?.trim()) {
    return NextResponse.json({ error: "title is required" }, { status: 400 });
  }
  try {
    const result = await writeNote({
      type: body.type,
      title: body.title,
      body: body.body ?? "",
      project: body.project,
      tags: body.tags,
      scope: body.scope,
    });
    return NextResponse.json(result, { status: 201 });
  } catch (err) {
    return NextResponse.json({ error: (err as Error).message }, { status: 500 });
  }
}
