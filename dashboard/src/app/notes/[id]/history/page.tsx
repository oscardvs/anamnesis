import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { NoteHistoryExplorer } from "@/components/note-history-explorer";
import { PageHeader } from "@/components/ui/misc";
import { noteHistory } from "@/lib/git";
import { noteRelPath, readNote } from "@/lib/store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function NoteHistoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const note = await readNote(id);
  if (!note) notFound();
  const rel = noteRelPath(id);
  const commits = rel ? await noteHistory(rel) : [];

  return (
    <div className="animate-rise space-y-5">
      <Link
        href={`/notes/${id}`}
        className="inline-flex items-center gap-1.5 text-xs text-muted transition-colors hover:text-text"
      >
        <ArrowLeft size={14} strokeWidth={1.5} /> Back to note
      </Link>
      <PageHeader
        eyebrow="history"
        title={note.title || "(untitled)"}
        description="Version history for this note, with the diff each version introduced."
      />
      <NoteHistoryExplorer noteId={id} commits={commits} />
    </div>
  );
}
