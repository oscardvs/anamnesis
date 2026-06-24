import { cn } from "@/lib/cn";
import { MARK_CORE, MARK_PATH } from "@/lib/mark-path";

/**
 * Anamnesis "return" mark: a tapered spiral winding inward to an origin node
 * (recollection). Inherits the current text colour; defaults to the accent.
 */
export function BrandMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 100 100"
      className={cn("text-accent", className)}
      fill="currentColor"
      aria-hidden
    >
      <path d={MARK_PATH} />
      <circle cx="50" cy="50" r={MARK_CORE} />
    </svg>
  );
}
