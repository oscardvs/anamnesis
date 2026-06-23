import { NextResponse } from "next/server";

import { getMeta } from "@/lib/db";
import { deleteNote, readNote, writeNote, type WriteInput } from "@/lib/store";
import { MEMORY_TYPES } from "@/lib/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

interface Params {
  params: Promise<{ id: string }>;
}

/** GET /api/notes/:id - the full note (markdown body + metadata). */
export async function GET(_request: Request, { params }: Params) {
  const { id } = await params;
  const memory = await readNote(id);
  if (!memory) {
    return NextResponse.json({ error: "note not found" }, { status: 404 });
  }
  return NextResponse.json({ memory, meta: getMeta(id) });
}

/** PUT /api/notes/:id - update a note, commit it locally, and reindex. */
export async function PUT(request: Request, { params }: Params) {
  const { id } = await params;
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
      id,
      type: body.type,
      title: body.title,
      body: body.body ?? "",
      project: body.project,
      tags: body.tags,
      scope: body.scope,
    });
    return NextResponse.json(result);
  } catch (err) {
    return NextResponse.json({ error: (err as Error).message }, { status: 500 });
  }
}

/** DELETE /api/notes/:id - remove a note (file + commit + reindex). */
export async function DELETE(_request: Request, { params }: Params) {
  const { id } = await params;
  try {
    return NextResponse.json(await deleteNote(id));
  } catch (err) {
    return NextResponse.json({ error: (err as Error).message }, { status: 500 });
  }
}
