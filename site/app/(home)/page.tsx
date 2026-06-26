import Link from 'next/link';
import { CopyCommand } from '@/components/copy-command';
import { repoUrl, docsRoute } from '@/lib/shared';
import { Hero } from '@/components/landing/hero';
import { Demo } from '@/components/landing/demo';
import { InstallPill } from '@/components/landing/install-pill';
import { FeatureBento } from '@/components/landing/feature-bento';
import { HowItWorks } from '@/components/landing/how-it-works';
import { Comparison } from '@/components/landing/comparison';
import { SiteFooter } from '@/components/landing/site-footer';
import { Reveal } from '@/components/landing/reveal';
import { Icon, ICONS } from '@/components/landing/icons';

export default function Home() {
  return (
    <main className="grain relative flex flex-col">
      {/* 1. Hero: the promise, the subhead, the Amsterdam scenario, the CTAs. */}
      <Hero />

      {/* 1b. The recorded split-screen demo. */}
      <Demo />

      {/* 2. The one-line install pill (copy button). */}
      <InstallPill />

      {/* 3. Feature bento. Carries id="why" for the /#why nav anchor. */}
      <FeatureBento />

      {/* 4. Three-step how it works. */}
      <HowItWorks />

      {/* 5. Honest comparison block. */}
      <Comparison />

      {/* Final CTA */}
      <section className="relative overflow-hidden border-t border-line">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{ background: 'radial-gradient(ellipse at center, var(--accent-tint), transparent 70%)' }}
        />
        <div className="relative mx-auto max-w-3xl px-6 py-28 text-center">
          <Reveal>
            <h2 className="text-balance font-display text-4xl tracking-tight sm:text-5xl">
              Stop starting from zero on every machine.
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-fd-muted-foreground">
              Anamnesis keeps your coding agent&apos;s memory in markdown you own, synced over your
              own private network. Open source, local-first, no cloud account.
            </p>
            <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
              <Link
                href={docsRoute}
                className="tap sheen inline-flex items-center gap-2 rounded-full bg-accent-gradient px-5 py-2.5 font-medium text-accent-contrast"
              >
                Read the docs
                <Icon path={ICONS.arrow} size={18} />
              </Link>
              <Link
                href={repoUrl}
                target="_blank"
                rel="noreferrer"
                className="tap bezel inline-flex items-center gap-2 rounded-full bg-surface/70 px-5 py-2.5 font-medium text-fd-foreground transition-colors hover:border-accent/40"
              >
                <Icon path={ICONS.github} size={18} className="text-fd-muted-foreground" />
                View on GitHub
              </Link>
            </div>
            <div className="mt-8 flex justify-center">
              <CopyCommand />
            </div>
          </Reveal>
        </div>
      </section>

      {/* 6. Open-source footer: Apache-2.0, GitHub, llms.txt. */}
      <SiteFooter />
    </main>
  );
}
