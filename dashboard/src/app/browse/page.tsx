import { NoteBrowser } from "@/components/note-browser";
import { PageHeader } from "@/components/ui/misc";
import { listMeta } from "@/lib/db";
import { MEMORY_TYPES, type MemoryType } from "@/lib/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export default async function BrowsePage({
  searchParams,
}: {
  searchParams: Promise<{ project?: string; type?: string }>;
}) {
  const sp = await searchParams;
  const project = sp.project ?? null;
  const type = MEMORY_TYPES.includes(sp.type as MemoryType) ? (sp.type as MemoryType) : null;
  const initialNotes = listMeta({
    project: project ?? undefined,
    type: type ?? undefined,
    limit: 300,
  });

  return (
    <div className="animate-rise space-y-6">
      <PageHeader
        eyebrow="memory"
        title="Browse"
        description="Full-text search across every note, backed by the SQLite FTS5 (BM25) index."
      />
      <NoteBrowser initialNotes={initialNotes} project={project} initialType={type} />
    </div>
  );
}
