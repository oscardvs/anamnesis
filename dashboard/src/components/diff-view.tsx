import { FileText } from "lucide-react";

import { cn } from "@/lib/cn";
import type { DiffLine } from "@/lib/types";

const CHANGE_LABEL: Record<string, string> = {
  A: "added",
  M: "modified",
  D: "deleted",
  R: "renamed",
  T: "type changed",
};

/** A GitHub-style two-gutter line diff for a single note. */
export function DiffView({ lines, className }: { lines: DiffLine[]; className?: string }) {
  if (lines.length === 0) {
    return (
      <div className={cn("rounded-xl bezel bg-surface px-4 py-8 text-center text-xs text-faint", className)}>
        No changes between these versions.
      </div>
    );
  }
  return (
    <div className={cn("overflow-x-auto rounded-xl bezel bg-surface", className)}>
      <table className="w-full border-collapse font-mono text-[12.5px] leading-[1.65]">
        <tbody>
          {lines.map((l, i) => (
            <tr
              key={i}
              className={cn(
                l.type === "add" && "bg-add-tint",
                l.type === "del" && "bg-del-tint",
              )}
            >
              <td className="w-10 select-none border-r border-line px-2 text-right align-top text-[11px] text-faint">
                {l.oldNumber ?? ""}
              </td>
              <td className="w-10 select-none border-r border-line px-2 text-right align-top text-[11px] text-faint">
                {l.newNumber ?? ""}
              </td>
              <td
                className="w-5 select-none px-1 text-center align-top font-medium"
                style={{
                  color:
                    l.type === "add"
                      ? "var(--add)"
                      : l.type === "del"
                        ? "var(--del)"
                        : "transparent",
                }}
              >
                {l.type === "add" ? "+" : l.type === "del" ? "-" : ""}
              </td>
              <td className="whitespace-pre-wrap break-words px-2 py-px align-top text-text">
                {l.content || " "}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A diff with a file header (path + change type + +/- counts). */
export function FileDiffCard({
  path,
  changeType,
  additions,
  deletions,
  lines,
  className,
}: {
  path: string;
  changeType: string;
  additions: number;
  deletions: number;
  lines: DiffLine[];
  className?: string;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex flex-wrap items-center gap-2 px-0.5">
        <FileText size={14} strokeWidth={1.5} className="text-faint" />
        <span className="font-mono text-[12.5px] text-muted">{path}</span>
        <span className="text-[11px] text-faint">{CHANGE_LABEL[changeType] ?? changeType}</span>
        <span className="ml-auto flex items-center gap-2 font-mono text-[11px]">
          {additions > 0 && <span style={{ color: "var(--add)" }}>+{additions}</span>}
          {deletions > 0 && <span style={{ color: "var(--del)" }}>-{deletions}</span>}
        </span>
      </div>
      <DiffView lines={lines} />
    </div>
  );
}
