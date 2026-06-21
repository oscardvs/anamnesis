"use client";

import { useEffect, useRef, useState } from "react";

import Link from "next/link";
import { Inbox, Search, X } from "lucide-react";

import { NoteRow } from "@/components/note-row";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { cn } from "@/lib/cn";
import { shortProject } from "@/lib/format";
import { MEMORY_TYPES, type MemoryMeta, type MemoryType } from "@/lib/types";

export function NoteBrowser({
  initialNotes,
  project,
  initialType,
}: {
  initialNotes: MemoryMeta[];
  project: string | null;
  initialType: MemoryType | null;
}) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState<MemoryType | null>(initialType);
  const [notes, setNotes] = useState<MemoryMeta[]>(initialNotes);
  const [loading, setLoading] = useState(false);
  const skipFirst = useRef(true);

  useEffect(() => {
    if (skipFirst.current) {
      skipFirst.current = false;
      return; // SSR already provided the initial list for these filters
    }
    setLoading(true);
    const handle = setTimeout(
      async () => {
        const params = new URLSearchParams();
        if (query.trim()) params.set("q", query.trim());
        if (type) params.set("type", type);
        if (project) params.set("project", project);
        params.set("limit", "300");
        try {
          const res = await fetch(`/api/notes?${params.toString()}`, { cache: "no-store" });
          const data = (await res.json()) as { notes: MemoryMeta[] };
          setNotes(data.notes);
        } catch {
          setNotes([]);
        } finally {
          setLoading(false);
        }
      },
      query ? 160 : 0,
    );
    return () => clearTimeout(handle);
  }, [query, type, project]);

  const filters: { label: string; value: MemoryType | null }[] = [
    { label: "All", value: null },
    ...MEMORY_TYPES.map((t) => ({ label: t, value: t })),
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search
            size={15}
            strokeWidth={1.5}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint"
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={project ? `Search in ${shortProject(project)}...` : "Search memory (BM25)..."}
            className="h-9 w-full rounded-lg bezel bg-surface-2 pl-9 pr-3 text-sm text-text outline-none transition-colors placeholder:text-faint focus-visible:ring-2 focus-visible:ring-accent/50"
          />
          {loading && <Spinner className="absolute right-3 top-1/2 -translate-y-1/2 size-3.5" />}
        </div>
        <div className="flex items-center gap-1 rounded-lg bezel bg-surface-2 p-1">
          {filters.map((f) => (
            <button
              key={f.label}
              onClick={() => setType(f.value)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors",
                type === f.value ? "bg-accent-tint text-accent" : "text-muted hover:text-text",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {project && (
        <div className="flex items-center gap-2 text-xs text-muted">
          <span>Filtered to</span>
          <span className="font-mono text-text">{shortProject(project)}</span>
          <Link
            href="/browse"
            className="inline-flex items-center gap-1 rounded-full bezel bg-surface-2 px-2 py-0.5 text-faint transition-colors hover:text-text"
          >
            clear <X size={11} strokeWidth={2} />
          </Link>
        </div>
      )}

      <p className="px-1 text-[11px] uppercase tracking-[0.12em] text-faint">
        {notes.length} note{notes.length === 1 ? "" : "s"}
      </p>

      {notes.length === 0 ? (
        <EmptyState
          icon={<Inbox />}
          title={query ? "No matches" : "No memory here yet"}
          description={
            query
              ? "Try a different search term."
              : "Create a note, or let Claude Code capture sessions into this store."
          }
        />
      ) : (
        <div className="rounded-2xl bezel bg-surface p-1.5">
          <div className="divide-y divide-line">
            {notes.map((note) => (
              <NoteRow key={note.id} note={note} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
