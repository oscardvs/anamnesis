// site/components/landing/demo.tsx
import { asset } from '@/lib/asset';

// Real recorded split-screen Amsterdam demo: desktop writes context, laptop
// recalls it. Autoplay-muted loop (works without JS). The .mp4 is produced by
// the manual recording step (see bench/cross-machine-tokens/RUNBOOK.md) and
// swapped in before launch; until then the poster shows a recording-in-progress
// placeholder.
export function Demo() {
  return (
    <section className="mx-auto w-full max-w-5xl px-4 py-10 sm:py-16">
      <div className="bezel grain overflow-hidden rounded-2xl bg-surface">
        <video
          className="block w-full"
          poster={asset('/demo-poster.svg')}
          autoPlay
          muted
          loop
          playsInline
          preload="none"
        >
          <source src={asset('/demo.mp4')} type="video/mp4" />
          <a href={asset('/demo.mp4')} className="text-accent underline">
            Watch the cross-machine demo
          </a>
        </video>
      </div>
      <p className="mt-3 text-center text-sm text-muted">
        Desktop teaches the conventions; the laptop, 1,000 km away, already knows them.
      </p>
    </section>
  );
}
