/** Anamnesis mark: three stacked isometric plates - memory layers that sync. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" aria-hidden>
      <path d="M12 2 L21 7 L12 12 L3 7 Z" fill="var(--accent)" fillOpacity="0.92" />
      <path
        d="M3 12 L12 17 L21 12"
        stroke="var(--accent)"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.72"
      />
      <path
        d="M3 17 L12 22 L21 17"
        stroke="var(--accent)"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.42"
      />
    </svg>
  );
}
