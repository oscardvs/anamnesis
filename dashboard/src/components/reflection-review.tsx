"use client";

import { useState } from "react";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { ProvenanceBadge } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/misc";
import { relativeTime, shortProject } from "@/lib/format";
import type { MemoryMeta } from "@/lib/types";

export function ReflectionReview({ initialNotes }: { initialNotes: MemoryMeta[] }) {
  const [notes, setNotes] = useState<MemoryMeta[]>(initialNotes);
  const [busy, setBusy] = useState<string | null>(null);
  const router = useRouter();

  const act = async (id: string, url: string, method: string, okMsg: string, failMsg: string) => {
    setBusy(id);
    try {
      const res = await fetch(url, { method });
      if (!res.ok) throw new Error();
      setNotes((n) => n.filter((x) => x.id !== id));
      toast.success(okMsg);
      router.refresh();
    } catch {
      toast.error(failMsg);
    } finally {
      setBusy(null);
    }
  };

  if (notes.length === 0) {
    return (
      <EmptyState
        icon={<Sparkles />}
        title="No reflections awaiting review"
        description="Run Reflect to distill this fleet's episodic notes into durable memory."
      />
    );
  }

  return (
    <div className="rounded-2xl bezel bg-surface p-1.5 shadow-[var(--shadow)]">
      <div className="divide-y divide-line">
        {notes.map((note) => (
          <div key={note.id} className="flex items-start gap-3 px-3 py-3">
            <div className="min-w-0 flex-1">
              <Link
                href={`/notes/${note.id}`}
                className="block truncate text-[14px] font-medium text-text transition-colors hover:text-accent"
              >
                {note.title || "(untitled)"}
              </Link>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-faint">
                <span className="text-muted">{shortProject(note.project)}</span>
                <span aria-hidden>·</span>
                <span>updated {relativeTime(note.updatedAt)}</span>
                <ProvenanceBadge source={note.provSource} confidence={note.confidence} />
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <Button
                variant="secondary"
                size="sm"
                disabled={busy === note.id}
                onClick={() => act(note.id, `/api/notes/${note.id}/keep`, "POST", "Kept (marked reviewed)", "Could not keep note")}
              >
                <Check strokeWidth={1.5} /> Keep
              </Button>
              <Button
                variant="danger"
                size="sm"
                disabled={busy === note.id}
                onClick={() => act(note.id, `/api/notes/${note.id}`, "DELETE", "Deleted", "Could not delete note")}
              >
                <Trash2 strokeWidth={1.5} /> Delete
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
