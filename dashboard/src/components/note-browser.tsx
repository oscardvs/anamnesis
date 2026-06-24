"use client";

import { useEffect, useRef, useState } from "react";

import Link from "next/link";
import { Inbox, Search, X } from "lucide-react";

import { CliPreviewButton } from "@/components/cli-preview-button";
import { NoteCard } from "@/components/note-card";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { cn } from "@/lib/cn";
import { shortProject } from "@/lib/format";
import { MEMORY_TYPES, type MemoryMeta, type MemoryType } from "@/lib/types";

const TYPE_VARS: Record<MemoryType, string> = {
  semantic: "var(--type-semantic)",
  procedural: "var(--type-procedural)",
  episodic: "var(--type-episodic)",
};

export function NoteBrowser({
  initialNotes,
  project,
  initialType,
  counts,
}: {
  initialNotes: MemoryMeta[];
  project: string | null;
  initialType: MemoryType | null;
  counts: { total: number; byType: Record<string, number> };
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

  return (
    <div className="space-y-5">
      <div className="relative max-w-md">
        <Search
          size={15}
          strokeWidth={1.5}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint"
        />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={project ? `Search in ${shortProject(project)}...` : "Search memory (BM25)..."}
          className="h-10 w-full rounded-xl border border-line bg-surface-2 pl-9 pr-3 text-sm text-text outline-none transition-[border-color,box-shadow] placeholder:text-faint focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-tint)]"
        />
        {loading && <Spinner className="absolute right-3 top-1/2 size-3.5 -translate-y-1/2" />}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setType(null)}
          className={cn(
            "tap flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
            type === null
              ? "bg-accent text-accent-contrast"
              : "border border-line bg-surface text-muted hover:text-text",
          )}
        >
          All <span className="font-mono opacity-70">{counts.total}</span>
        </button>
        {MEMORY_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setType(t)}
            className={cn(
              "tap flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium capitalize transition-colors",
              type === t ? "border-transparent bg-accent-tint text-text" : "border-line bg-surface text-muted hover:text-text",
            )}
          >
            <span className="size-1.5 rounded-full" style={{ background: TYPE_VARS[t] }} />
            {t} <span className="font-mono opacity-70">{counts.byType[t] ?? 0}</span>
          </button>
        ))}
      </div>

      {project && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <span>Filtered to</span>
          <span className="font-mono text-text">{shortProject(project)}</span>
          <Link
            href="/browse"
            className="inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-0.5 text-faint transition-colors hover:text-text"
          >
            clear <X size={11} strokeWidth={2} />
          </Link>
          <div className="ml-auto">
            <CliPreviewButton
              label="Reflect project"
              endpoint="/api/reflect"
              buildQuery={(a) => `project=${encodeURIComponent(project)}${a ? "&apply=1" : ""}`}
            />
          </div>
        </div>
      )}

      <p className="px-0.5 text-[11px] uppercase tracking-[0.12em] text-faint">
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
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {notes.map((note) => (
            <NoteCard key={note.id} note={note} />
          ))}
        </div>
      )}
    </div>
  );
}
