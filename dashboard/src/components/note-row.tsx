import Link from "next/link";

import { ProvenanceBadge, TypeBadge } from "@/components/ui/badges";
import { relativeTime, shortProject } from "@/lib/format";
import type { MemoryMeta } from "@/lib/types";

/** A single note in a list: title, type, project, recency, a few tags. */
export function NoteRow({ note }: { note: MemoryMeta }) {
  return (
    <Link
      href={`/notes/${note.id}`}
      className="group flex items-start gap-3 rounded-xl px-3 py-3 transition-colors duration-150 hover:bg-highlight"
    >
      <div className="min-w-0 flex-1">
        <h3 className="truncate text-[14px] font-medium text-text">{note.title || "(untitled)"}</h3>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-faint">
          <span className="text-muted">{shortProject(note.project)}</span>
          <span aria-hidden>·</span>
          <span>updated {relativeTime(note.updatedAt)}</span>
          {note.tags.slice(0, 3).map((t) => (
            <span key={t} className="rounded bg-surface-2 px-1.5 py-0.5 text-faint">
              {t}
            </span>
          ))}
        </div>
      </div>
      <div className="mt-0.5 flex shrink-0 items-center gap-1.5">
        <TypeBadge type={note.type} />
        <ProvenanceBadge source={note.provSource} confidence={note.confidence} />
      </div>
    </Link>
  );
}
