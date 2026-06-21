import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { NoteEditor } from "@/components/note-editor";
import { PageHeader } from "@/components/ui/misc";
import { readNote } from "@/lib/store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function EditNotePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const note = await readNote(id);
  if (!note) notFound();

  return (
    <div className="animate-rise space-y-6">
      <Link
        href={`/notes/${id}`}
        className="inline-flex items-center gap-1.5 text-xs text-muted transition-colors hover:text-text"
      >
        <ArrowLeft size={14} strokeWidth={1.5} /> Back to note
      </Link>
      <PageHeader
        eyebrow="edit"
        title="Edit note"
        description="Changes write back to markdown, commit to the memory repo, and reindex."
      />
      <NoteEditor initial={note} />
    </div>
  );
}
