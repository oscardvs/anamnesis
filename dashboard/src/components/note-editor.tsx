"use client";

import { useEffect, useState } from "react";

import { useRouter } from "next/navigation";
import { Eye, PenLine, Save } from "lucide-react";
import { toast } from "sonner";

import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { cn } from "@/lib/cn";
import { MEMORY_TYPES, type Memory, type MemoryType, type Scope } from "@/lib/types";

const inputClass =
  "h-9 w-full rounded-lg bezel bg-surface-2 px-3 text-sm text-text outline-none transition-colors placeholder:text-faint focus-visible:ring-2 focus-visible:ring-accent/50";

const labelClass = "mb-1.5 block text-[11px] font-medium uppercase tracking-[0.12em] text-faint";

export function NoteEditor({ initial }: { initial?: Memory | null }) {
  const router = useRouter();
  const editing = Boolean(initial);

  const [title, setTitle] = useState(initial?.title ?? "");
  const [type, setType] = useState<MemoryType>(initial?.type ?? "semantic");
  const [project, setProject] = useState(initial?.project ?? "global");
  const [scope, setScope] = useState<Scope>(initial?.scope ?? "portable");
  const [tags, setTags] = useState((initial?.tags ?? []).join(", "));
  const [body, setBody] = useState(initial?.body ?? "");
  const [tab, setTab] = useState<"write" | "preview">("write");
  const [saving, setSaving] = useState(false);
  const [projects, setProjects] = useState<string[]>([]);

  useEffect(() => {
    fetch("/api/overview", { cache: "no-store" })
      .then((r) => r.json())
      .then((d: { stats?: { byProject?: Record<string, number> } }) =>
        setProjects(Object.keys(d.stats?.byProject ?? {})),
      )
      .catch(() => {});
  }, []);

  const save = async () => {
    if (!title.trim()) {
      toast.error("Title is required");
      return;
    }
    setSaving(true);
    const payload = {
      type,
      title: title.trim(),
      body,
      project: project.trim() || "global",
      scope,
      tags: tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    };
    try {
      const res = await fetch(editing ? `/api/notes/${initial!.id}` : "/api/notes", {
        method: editing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const out = await res.json();
      if (!res.ok) {
        toast.error("Save failed", { description: out.error });
        return;
      }
      toast.success(editing ? "Note updated" : "Note created", {
        description: out.commit ? `committed ${out.commit}` : "saved and reindexed",
      });
      router.push(`/notes/${out.memory.id}`);
      router.refresh();
    } catch {
      toast.error("Save failed", { description: "Could not reach the dashboard API." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <label className={labelClass}>Title</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="A short, recall-friendly title"
          className={cn(inputClass, "h-11 text-base")}
          autoFocus
        />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label className={labelClass}>Type</label>
          <div className="flex items-center gap-1 rounded-lg bezel bg-surface-2 p-1">
            {MEMORY_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setType(t)}
                className={cn(
                  "flex-1 rounded-md px-2 py-1.5 text-xs font-medium capitalize transition-colors",
                  type === t ? "bg-accent-tint text-accent" : "text-muted hover:text-text",
                )}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className={labelClass}>Project</label>
          <input
            value={project}
            onChange={(e) => setProject(e.target.value)}
            list="projects"
            placeholder="global"
            className={inputClass}
          />
          <datalist id="projects">
            {projects.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>
        </div>
        <div>
          <label className={labelClass}>Scope</label>
          <div className="flex items-center gap-1 rounded-lg bezel bg-surface-2 p-1">
            {(["portable", "machine-local"] as Scope[]).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setScope(s)}
                className={cn(
                  "flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
                  scope === s ? "bg-accent-tint text-accent" : "text-muted hover:text-text",
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div>
        <label className={labelClass}>Tags</label>
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="comma, separated, tags"
          className={inputClass}
        />
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <label className={cn(labelClass, "mb-0")}>Body (markdown)</label>
          <div className="flex items-center gap-1 rounded-lg bezel bg-surface-2 p-1">
            <button
              type="button"
              onClick={() => setTab("write")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                tab === "write" ? "bg-accent-tint text-accent" : "text-muted hover:text-text",
              )}
            >
              <PenLine size={13} strokeWidth={1.5} /> Write
            </button>
            <button
              type="button"
              onClick={() => setTab("preview")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                tab === "preview" ? "bg-accent-tint text-accent" : "text-muted hover:text-text",
              )}
            >
              <Eye size={13} strokeWidth={1.5} /> Preview
            </button>
          </div>
        </div>
        {tab === "write" ? (
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Write the memory in markdown..."
            className={cn(
              inputClass,
              "min-h-[360px] resize-y py-3 font-mono text-[13px] leading-relaxed",
            )}
          />
        ) : (
          <div className="min-h-[360px] rounded-lg bezel bg-surface p-5">
            {body.trim() ? (
              <Markdown>{body}</Markdown>
            ) : (
              <p className="text-sm italic text-faint">Nothing to preview yet.</p>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-2">
        <Button variant="ghost" onClick={() => router.back()} disabled={saving}>
          Cancel
        </Button>
        <Button variant="primary" onClick={save} disabled={saving}>
          {saving ? <Spinner /> : <Save strokeWidth={1.5} />}
          {editing ? "Save changes" : "Create note"}
        </Button>
      </div>
    </div>
  );
}
