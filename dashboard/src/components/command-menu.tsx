"use client";

import { useEffect, useState } from "react";

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { FileText, GitCommitVertical, LayoutDashboard, Library, Plus, Server } from "lucide-react";

import { TypeBadge } from "@/components/ui/badges";
import { shortProject } from "@/lib/format";
import type { MemoryMeta } from "@/lib/types";

const NAV = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Browse memory", href: "/browse", icon: Library },
  { label: "History", href: "/history", icon: GitCommitVertical },
  { label: "Machines", href: "/machines", icon: Server },
  { label: "New note", href: "/notes/new", icon: Plus },
];

export function CommandMenu({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MemoryMeta[]>([]);
  const [loading, setLoading] = useState(false);

  // Debounced server-side FTS search; cmdk's own filter is disabled. Results are
  // only rendered while a query is present, so we never need to clear them here.
  useEffect(() => {
    const q = query.trim();
    if (!q) return;
    const id = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/notes?q=${encodeURIComponent(q)}&limit=12`, {
          cache: "no-store",
        });
        const data = (await res.json()) as { notes: MemoryMeta[] };
        setResults(data.notes);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 150);
    return () => clearTimeout(id);
  }, [query]);

  const handleOpenChange = (next: boolean) => {
    if (!next) setQuery("");
    onOpenChange(next);
  };

  const go = (href: string) => {
    handleOpenChange(false);
    router.push(href);
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={handleOpenChange}
      shouldFilter={false}
      label="Command menu"
      className="flex flex-col"
      overlayClassName="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
      contentClassName="fixed left-1/2 top-[18%] z-50 w-[min(92vw,560px)] -translate-x-1/2 overflow-hidden rounded-2xl bezel bg-elevated shadow-[0_24px_60px_-12px_rgba(0,0,0,0.5)] animate-rise"
    >
      <div className="flex items-center gap-2 border-b border-line px-4">
        <Library size={16} strokeWidth={1.5} className="text-faint" />
        <Command.Input
          value={query}
          onValueChange={setQuery}
          placeholder="Search memory or jump to a view..."
          className="h-12 w-full bg-transparent text-sm text-text outline-none placeholder:text-faint"
        />
      </div>
      <Command.List className="max-h-[min(60vh,420px)] overflow-y-auto p-2">
        {!query.trim() && (
          <Command.Group heading="Go to">
            {NAV.map((item) => (
              <Command.Item
                key={item.href}
                value={item.label}
                onSelect={() => go(item.href)}
                className="cmd-item"
              >
                <item.icon size={16} strokeWidth={1.5} className="text-faint" />
                {item.label}
              </Command.Item>
            ))}
          </Command.Group>
        )}

        {query.trim() && (
          <Command.Group
            heading={loading ? "Searching..." : `${results.length} result${results.length === 1 ? "" : "s"}`}
          >
            {results.length === 0 && !loading && (
              <Command.Empty className="px-3 py-6 text-center text-xs text-faint">
                No memory matches &ldquo;{query.trim()}&rdquo;.
              </Command.Empty>
            )}
            {results.map((note) => (
              <Command.Item
                key={note.id}
                value={note.id}
                onSelect={() => go(`/notes/${note.id}`)}
                className="cmd-item"
              >
                <FileText size={16} strokeWidth={1.5} className="shrink-0 text-faint" />
                <span className="min-w-0 flex-1 truncate text-text">{note.title}</span>
                <span className="hidden shrink-0 text-[11px] text-faint sm:inline">
                  {shortProject(note.project)}
                </span>
                <TypeBadge type={note.type} />
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
}
