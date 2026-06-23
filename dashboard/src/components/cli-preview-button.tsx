"use client";

import { useState } from "react";

import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button, type ButtonProps } from "@/components/ui/button";
import { Panel, Spinner } from "@/components/ui/misc";

interface CliRun {
  ok: boolean;
  output: string;
}

const NO_PROVIDER = "no reflection provider configured";

/** A button that runs a CLI dry-run, shows the output verbatim, then offers Apply. */
export function CliPreviewButton({
  label,
  endpoint,
  buildQuery = () => "",
  variant = "secondary",
  icon = <Sparkles strokeWidth={1.5} />,
  onApplied,
}: {
  label: string;
  endpoint: string;
  /** Returns the query string (without `?`) for a dry-run (apply=false) or apply (apply=true). */
  buildQuery?: (apply: boolean) => string;
  variant?: ButtonProps["variant"];
  icon?: React.ReactNode;
  onApplied?: () => void;
}) {
  const [output, setOutput] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [applying, setApplying] = useState(false);
  const router = useRouter();

  const post = async (apply: boolean): Promise<CliRun> => {
    const qs = buildQuery(apply);
    const res = await fetch(`${endpoint}${qs ? `?${qs}` : ""}`, { method: "POST" });
    return (await res.json()) as CliRun;
  };

  const dryRun = async () => {
    setRunning(true);
    try {
      const r = await post(false);
      setOutput(r.output || "Nothing to do.");
    } catch {
      toast.error(`${label} failed`, { description: "Could not reach the anamnesis CLI." });
    } finally {
      setRunning(false);
    }
  };

  const apply = async () => {
    setApplying(true);
    try {
      const r = await post(true);
      if (r.output.includes(NO_PROVIDER)) {
        toast.error("No reflection provider configured", {
          description: "Set ANAMNESIS_REFLECTION_PROVIDER + model/base-url and DEEPSEEK_API_KEY in the dashboard's environment.",
        });
        setOutput(r.output);
        return;
      }
      if (!r.ok) {
        toast.error(`${label} failed`, { description: r.output.slice(0, 200) });
        setOutput(r.output);
        return;
      }
      toast.success(`${label} applied`, { description: r.output.slice(0, 200) || undefined });
      setOutput(null);
      onApplied?.();
      router.refresh();
    } catch {
      toast.error(`${label} failed`);
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="flex flex-col items-stretch gap-2">
      <div className="flex items-center gap-2">
        <Button variant={variant} size="sm" onClick={dryRun} disabled={running || applying}>
          {running ? <Spinner /> : icon}
          {label}
        </Button>
        {output !== null && (
          <Button variant="ghost" size="sm" onClick={() => setOutput(null)} disabled={applying}>
            Close
          </Button>
        )}
      </div>
      {output !== null && (
        <Panel className="p-3">
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] text-muted">
            {output}
          </pre>
          <div className="mt-3 flex justify-end">
            <Button variant="primary" size="sm" onClick={apply} disabled={applying}>
              {applying ? <Spinner /> : null}
              Apply
            </Button>
          </div>
        </Panel>
      )}
    </div>
  );
}
