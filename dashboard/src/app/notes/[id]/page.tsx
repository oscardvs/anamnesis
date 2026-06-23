import Link from "next/link";
import { notFound } from "next/navigation";
import { GitCommitVertical, Pencil } from "lucide-react";

import { Markdown } from "@/components/markdown";
import { ProvenanceBadge, TypeBadge } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/misc";
import { noteHistory } from "@/lib/git";
import { absoluteTime, relativeTime, shortProject } from "@/lib/format";
import { noteRelPath, readNote } from "@/lib/store";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function MetaItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 py-2">
      <dt className="text-[10px] font-medium uppercase tracking-[0.12em] text-faint">{label}</dt>
      <dd className="break-words text-[13px] text-text">{children}</dd>
    </div>
  );
}

export default async function NotePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const note = await readNote(id);
  if (!note) notFound();
  const rel = noteRelPath(id);
  const commits = rel ? await noteHistory(rel) : [];

  return (
    <div className="animate-rise space-y-6">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <TypeBadge type={note.type} />
          <ProvenanceBadge source={note.provSource} confidence={note.confidence} />
          <Link
            href={`/browse?project=${encodeURIComponent(note.project)}`}
            className="font-mono text-faint transition-colors hover:text-text"
          >
            {shortProject(note.project)}
          </Link>
        </div>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-text">
            {note.title || "(untitled)"}
          </h1>
          <div className="flex shrink-0 items-center gap-2">
            <Button variant="secondary" asChild>
              <Link href={`/notes/${id}/history`}>
                <GitCommitVertical strokeWidth={1.5} /> History
                <span className="font-mono text-xs text-faint">{commits.length}</span>
              </Link>
            </Button>
            <Button variant="primary" asChild>
              <Link href={`/notes/${id}/edit`}>
                <Pencil strokeWidth={1.5} /> Edit
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_280px]">
        <Panel className="p-6 lg:p-7">
          {note.body.trim() ? (
            <Markdown>{note.body}</Markdown>
          ) : (
            <p className="text-sm italic text-faint">This note has no body.</p>
          )}
        </Panel>

        <aside className="lg:sticky lg:top-20 lg:self-start">
          <Panel className="px-4 py-2">
            <dl className="divide-y divide-line">
              <MetaItem label="Type">
                <span className="capitalize">{note.type}</span>
              </MetaItem>
              <MetaItem label="Project">
                <span className="font-mono text-[12px]">{note.project}</span>
              </MetaItem>
              <MetaItem label="Machine of origin">{note.machineId}</MetaItem>
              <MetaItem label="Scope">{note.scope}</MetaItem>
              <MetaItem label="Provenance">
                <span className="capitalize">{note.provSource}</span>
                <span className="text-faint"> · {note.confidence}</span>
                {note.provModel && (
                  <span className="block font-mono text-[11px] text-muted">{note.provModel}</span>
                )}
                {note.provSession && (
                  <span className="block font-mono text-[11px] text-faint">
                    session {note.provSession}
                  </span>
                )}
              </MetaItem>
              <MetaItem label="Updated">
                <span title={absoluteTime(note.updatedAt)}>{relativeTime(note.updatedAt)}</span>
              </MetaItem>
              <MetaItem label="Created">
                <span title={absoluteTime(note.createdAt)}>{absoluteTime(note.createdAt)}</span>
              </MetaItem>
              <MetaItem label="ID">
                <span className="font-mono text-[11px] text-muted">{note.id}</span>
              </MetaItem>
              {note.tags.length > 0 && (
                <MetaItem label="Tags">
                  <div className="flex flex-wrap gap-1">
                    {note.tags.map((t) => (
                      <span
                        key={t}
                        className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-muted"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </MetaItem>
              )}
            </dl>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
