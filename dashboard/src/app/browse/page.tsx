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

  // One scoped query drives both the counts (type-unfiltered) and the initial list.
  const scoped = listMeta({ project: project ?? undefined, limit: 5000 });
  const byType: Record<string, number> = {};
  for (const t of MEMORY_TYPES) byType[t] = 0;
  for (const n of scoped) byType[n.type] = (byType[n.type] ?? 0) + 1;
  const counts = { total: scoped.length, byType };
  const initialNotes = (type ? scoped.filter((n) => n.type === type) : scoped).slice(0, 300);

  return (
    <div className="animate-rise space-y-6">
      <PageHeader
        eyebrow="library"
        title="Browse"
        description={`${counts.total} memories${project ? " in this project" : " across every project"}, every note a markdown file under version control.`}
      />
      <NoteBrowser
        initialNotes={initialNotes}
        project={project}
        initialType={type}
        counts={counts}
      />
    </div>
  );
}
