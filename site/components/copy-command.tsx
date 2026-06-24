'use client';

import { useState } from 'react';
import { installCommand } from '@/lib/shared';

export function CopyCommand({
  command = installCommand,
  className = '',
}: {
  command?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard?.writeText(command).then(
          () => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1600);
          },
          () => {},
        );
      }}
      aria-label={`Copy install command: ${command}`}
      className={`tap sheen bezel group inline-flex max-w-full items-center gap-3 rounded-full bg-surface/70 py-2 pl-4 pr-2 font-mono text-sm transition-colors hover:border-accent/40 ${className}`}
    >
      <span aria-hidden className="select-none text-accent">$</span>
      <span className="min-w-0 truncate text-fd-foreground">{command}</span>
      <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-fd-foreground/5 transition-transform duration-300 group-hover:scale-105">
        {copied ? (
          <svg
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-accent"
            aria-hidden
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
        ) : (
          <svg
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-fd-muted-foreground"
            aria-hidden
          >
            <rect x="9" y="9" width="11" height="11" rx="2.5" />
            <path d="M5 15V5a2 2 0 0 1 2-2h10" />
          </svg>
        )}
      </span>
    </button>
  );
}
