import { MARK_PATH } from '@/lib/mark-path';

export function Wordmark() {
  return (
    <span className="inline-flex items-center gap-2 font-display font-semibold">
      <svg viewBox="0 0 100 100" aria-hidden className="h-5 w-5" style={{ fill: 'currentColor' }}>
        <path d={MARK_PATH} />
      </svg>
      Anamnesis
    </span>
  );
}
