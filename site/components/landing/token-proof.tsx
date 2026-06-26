// site/components/landing/token-proof.tsx
import { asset } from '@/lib/asset';
import { repoUrl } from '@/lib/shared';

// The proof beat: our own measured before/after for completing one task on a
// fresh machine, cold vs with Anamnesis's injected memory. The SVG is generated
// by bench/cross-machine-tokens (a sample until the real run is committed).
export function TokenProof() {
  return (
    <section id="proof" className="mx-auto w-full max-w-4xl px-4 py-14 sm:py-20">
      <h2 className="text-balance font-display text-2xl tracking-tight sm:text-3xl">
        The same task costs less on a fresh machine.
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
        Tokens to finish one scripted task on a clean machine: without Anamnesis the
        agent re-explores the project to learn its conventions; with Anamnesis the
        SessionStart memory block carries them over.
      </p>
      <div className="bezel mt-6 overflow-hidden rounded-2xl bg-surface p-4">
        <img
          src={asset('/token-chart.svg')}
          alt="Tokens to complete the task without vs with Anamnesis"
          className="mx-auto block w-full max-w-2xl"
          width={720}
          height={360}
        />
      </div>
      <p className="mt-3 text-xs text-faint">
        Measured with the Claude Agent SDK on a synthetic project, averaged over
        several runs.{' '}
        <a
          href={`${repoUrl}/tree/main/bench/cross-machine-tokens`}
          className="text-accent underline"
        >
          Reproduce it
        </a>
        .
      </p>
    </section>
  );
}
