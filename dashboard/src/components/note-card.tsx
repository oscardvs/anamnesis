import Link from "next/link";

import { ProvenanceBadge, TypeBadge } from "@/components/ui/badges";
import { relativeTime, shortProject } from "@/lib/format";
import type { MemoryMeta } from "@/lib/types";

/** A note as a grid card: type + recency, mono title, project, tags, provenance. */
export function NoteCard({ note }: { note: MemoryMeta }) {
  return (
    <Link
      href={`/notes/${note.id}`}
      className="lift group flex flex-col rounded-2xl border border-line bg-surface p-4 shadow-[var(--shadow)] transition-colors hover:border-accent"
    >
      <div className="mb-2.5 flex items-start justify-between gap-2">
        <TypeBadge type={note.type} />
        <span className="shrink-0 text-[11px] text-faint">{relativeTime(note.updatedAt)}</span>
      </div>
      <h3 className="line-clamp-2 font-mono text-[14px] font-semibold leading-snug text-text">
        {note.title || "(untitled)"}
      </h3>
      <p className="mt-1.5 text-[11.5px] text-faint">{shortProject(note.project)}</p>
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        {note.tags.slice(0, 3).map((t) => (
          <span
            key={t}
            className="rounded-md border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-muted"
          >
            {t}
          </span>
        ))}
        <ProvenanceBadge source={note.provSource} confidence={note.confidence} className="ml-auto" />
      </div>
    </Link>
  );
}
