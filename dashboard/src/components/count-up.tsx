"use client";

import { useEffect, useRef, useState } from "react";

/** Counts up to `value` on mount (eased). SSR/no-JS/reduced-motion show the final value. */
export function CountUp({
  value,
  className,
  style,
}: {
  value: number;
  className?: string;
  style?: React.CSSProperties;
}) {
  const [n, setN] = useState(value);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    // Initial state already equals `value` (SSR / no-JS / reduced-motion safe).
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const dur = 900;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      setN(Math.round(eased * value));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return (
    <span className={className} style={style}>
      {n.toLocaleString()}
    </span>
  );
}
