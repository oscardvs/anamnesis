"use client";

import { useCallback, useEffect, useState } from "react";

import { RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { StatusDot } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { describeRepo } from "@/lib/repo";
import type { RepoState } from "@/lib/types";

interface SyncOutcome {
  pushed: boolean;
  pulled: number;
  conflicted: boolean;
  detail: string;
}

export function SyncControl() {
  const [repo, setRepo] = useState<RepoState | null>(null);
  const [syncing, setSyncing] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/fleet", { cache: "no-store" });
      const data = (await res.json()) as { repo: RepoState };
      setRepo(data.repo);
    } catch {
      /* leave last known state */
    }
  }, []);

  useEffect(() => {
    const initial = setTimeout(refresh, 0);
    const id = setInterval(refresh, 20_000);
    return () => {
      clearTimeout(initial);
      clearInterval(id);
    };
  }, [refresh]);

  const onSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch("/api/sync", { method: "POST" });
      const out = (await res.json()) as SyncOutcome;
      if (out.conflicted) {
        toast.error("Sync conflict", {
          description: out.detail || "Resolve in the memory repo, then sync again.",
        });
      } else {
        const parts = [];
        if (out.pushed) parts.push("pushed local edits");
        if (out.pulled) parts.push(`pulled ${out.pulled}`);
        toast.success("Synced", { description: parts.join(" + ") || out.detail || "up to date" });
      }
      await refresh();
    } catch {
      toast.error("Sync failed", { description: "Could not reach the anamnesis CLI." });
    } finally {
      setSyncing(false);
    }
  };

  const { label, tone } = describeRepo(repo);
  return (
    <div className="flex items-center gap-1.5">
      <div className="hidden items-center gap-1.5 rounded-full bezel bg-surface-2 px-2.5 py-1 sm:flex">
        <StatusDot tone={tone} pulse={tone === "danger"} />
        <span className="text-[11px] font-medium text-muted">{label}</span>
      </div>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={onSync}
        disabled={syncing}
        aria-label="Sync now"
        title="Sync now (pull + push)"
      >
        {syncing ? <Spinner /> : <RefreshCw strokeWidth={1.5} />}
      </Button>
    </div>
  );
}
