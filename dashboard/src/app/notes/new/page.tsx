import { NoteEditor } from "@/components/note-editor";
import { PageHeader } from "@/components/ui/misc";

export const dynamic = "force-dynamic";

export default function NewNotePage() {
  return (
    <div className="animate-rise space-y-6">
      <PageHeader
        eyebrow="create"
        title="New note"
        description="Write a memory directly. It is saved as markdown, committed locally, and reindexed."
      />
      <NoteEditor />
    </div>
  );
}
