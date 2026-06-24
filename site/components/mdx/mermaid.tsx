'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { useTheme } from 'next-themes';

let mermaidLoader: Promise<typeof import('mermaid').default> | null = null;

function loadMermaid() {
  if (!mermaidLoader) {
    mermaidLoader = import('mermaid').then((m) => m.default);
  }
  return mermaidLoader;
}

/* Mermaid 11 (via khroma) can't parse CSS Color-4 syntax like oklch() or lab(),
   which is what the browser resolves our --color-fd-* vars into. So we mirror
   the palette here as plain hex and switch by theme. */
// Keep in sync with app/global.css Recollection palette.
const PALETTE = {
  light: {
    bg: '#f3f1f8', fg: '#2a2733', muted: '#ece9f3', mutedFg: '#6b6478',
    card: '#fbfaff', border: '#d7d2e3', primary: '#6046d6', primaryFg: '#fbfaff',
  },
  dark: {
    bg: '#181527', fg: '#eceaf4', muted: '#2a2740', mutedFg: '#9d97b5',
    card: '#221f33', border: '#3a3552', primary: '#a896ff', primaryFg: '#101019',
  },
} as const;

export function Mermaid({ chart }: { chart: string }) {
  const id = useId().replace(/:/g, '_');
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!mounted) return;
    let cancelled = false;

    loadMermaid().then(async (mermaid) => {
      const t = PALETTE[resolvedTheme === 'dark' ? 'dark' : 'light'];

      try {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          theme: 'base',
          fontFamily: 'var(--font-mono), ui-monospace, monospace',
          themeVariables: {
            fontFamily: 'var(--font-mono), ui-monospace, monospace',
            fontSize: '13px',
            background: t.bg,

            primaryColor: t.card,
            primaryTextColor: t.fg,
            primaryBorderColor: t.mutedFg,

            secondaryColor: t.muted,
            secondaryTextColor: t.fg,
            secondaryBorderColor: t.border,

            tertiaryColor: t.bg,
            tertiaryTextColor: t.fg,
            tertiaryBorderColor: t.border,

            lineColor: t.primary,
            arrowheadColor: t.primary,
            textColor: t.fg,
            mainBkg: t.card,
            nodeBorder: t.mutedFg,
            clusterBkg: 'transparent',
            clusterBorder: t.border,
            edgeLabelBackground: t.bg,
            titleColor: t.fg,

            actorBkg: t.card,
            actorBorder: t.mutedFg,
            actorTextColor: t.fg,
            actorLineColor: t.border,
            signalColor: t.fg,
            signalTextColor: t.fg,
            labelBoxBkgColor: t.card,
            labelBoxBorderColor: t.border,
            labelTextColor: t.fg,
            activationBorderColor: t.primary,
            activationBkgColor: t.card,
            sequenceNumberColor: t.primaryFg,
            noteBkgColor: t.muted,
            noteBorderColor: t.border,
            noteTextColor: t.fg,
          },
        });

        const { svg, bindFunctions } = await mermaid.render(`mermaid-${id}`, chart);
        if (cancelled) return;
        setSvg(svg);
        setError(null);
        queueMicrotask(() => {
          if (containerRef.current && bindFunctions) bindFunctions(containerRef.current);
        });
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    });

    return () => {
      cancelled = true;
    };
  }, [chart, id, mounted, resolvedTheme]);

  if (error) {
    return (
      <pre className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap">
        Mermaid render error: {error}
      </pre>
    );
  }
  if (!svg) {
    return <div className="mermaid-frame my-6 h-24 animate-pulse" aria-hidden />;
  }

  return (
    <figure className="mermaid-frame my-6">
      <div
        ref={containerRef}
        className="flex justify-center [&_svg]:max-w-full [&_svg]:h-auto"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </figure>
  );
}
