import * as React from "react";

import { cn } from "@/lib/cn";
import { provenanceBadge } from "@/lib/provenance";
import type { MemoryType, ProvSource } from "@/lib/types";

type Tone = "neutral" | "accent" | "ok" | "warn" | "info" | "danger";

const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-muted",
  accent: "text-accent",
  ok: "text-ok",
  warn: "text-warn",
  info: "text-info",
  danger: "text-danger",
};

/** A small pill label. Neutral by default; tones tint the text. */
export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full bezel bg-surface-2 px-2 py-0.5 text-[11px] font-medium",
        TONE_TEXT[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** Quiet-by-default provenance chip: nothing for human, a tinted pill otherwise. */
export function ProvenanceBadge({
  source,
  confidence,
  className,
}: {
  source: ProvSource;
  confidence: number;
  className?: string;
}) {
  const b = provenanceBadge(source, confidence);
  if (!b) return null;
  return (
    <Badge tone={b.tone} className={className}>
      {b.label}
    </Badge>
  );
}

const TYPE_META: Record<MemoryType, { label: string; color: string }> = {
  procedural: { label: "procedural", color: "var(--type-procedural)" },
  semantic: { label: "semantic", color: "var(--type-semantic)" },
  episodic: { label: "episodic", color: "var(--type-episodic)" },
};

/** A memory-type chip: neutral pill with a hue-coded dot (calm, not rainbow). */
export function TypeBadge({ type, className }: { type: MemoryType; className?: string }) {
  const m = TYPE_META[type] ?? { label: type, color: "var(--faint)" };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full bezel bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-muted",
        className,
      )}
    >
      <span className="size-1.5 rounded-full" style={{ background: m.color }} />
      {m.label}
    </span>
  );
}

const DOT_COLOR: Record<Tone, string> = {
  neutral: "var(--faint)",
  accent: "var(--accent)",
  ok: "var(--ok)",
  warn: "var(--warn)",
  info: "var(--info)",
  danger: "var(--danger)",
};

/** A status dot with an optional soft pulse. */
export function StatusDot({
  tone = "neutral",
  pulse = false,
  className,
}: {
  tone?: Tone;
  pulse?: boolean;
  className?: string;
}) {
  const color = DOT_COLOR[tone];
  return (
    <span className={cn("relative inline-flex size-2", className)}>
      {pulse && (
        <span
          className="absolute inset-0 animate-ping rounded-full opacity-60"
          style={{ background: color }}
        />
      )}
      <span className="relative size-2 rounded-full" style={{ background: color }} />
    </span>
  );
}

export type { Tone };
