"use client";

import { useState } from "react";

import { useRouter } from "next/navigation";
import { RotateCw } from "lucide-react";
import { toast } from "sonner";

import { Button, type ButtonProps } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";

/** Rebuild the SQLite index from markdown, then refresh the current view. */
export function ReindexButton({
  label = "Reindex",
  variant = "secondary",
  size = "md",
}: {
  label?: string;
  variant?: ButtonProps["variant"];
  size?: ButtonProps["size"];
}) {
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const run = async () => {
    setBusy(true);
    try {
      const res = await fetch("/api/reindex", { method: "POST" });
      const out = (await res.json()) as { reindexed: boolean };
      if (out.reindexed) {
        toast.success("Reindexed from markdown");
        router.refresh();
      } else {
        toast.error("Reindex failed", { description: "Is the anamnesis CLI reachable?" });
      }
    } catch {
      toast.error("Reindex failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button variant={variant} size={size} onClick={run} disabled={busy}>
      {busy ? <Spinner /> : <RotateCw strokeWidth={1.5} />}
      {label}
    </Button>
  );
}
