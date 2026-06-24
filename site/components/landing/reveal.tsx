'use client';

import { useEffect, useRef, useState, type ReactNode, type Ref } from 'react';

/**
 * Fades + lifts its children into view when scrolled near the viewport,
 * reusing the `rise` keyframe defined in global.css. Content above the fold
 * reveals on mount; if IntersectionObserver is unavailable the content is
 * shown immediately so nothing is ever stuck hidden.
 */
export function Reveal({
  children,
  delay = 0,
  className = '',
  as: Tag = 'div',
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: 'div' | 'section' | 'li';
}) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === 'undefined') {
      setVisible(true);
      return;
    }
    const rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight && rect.bottom > 0) {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -8% 0px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const Component = Tag as 'div';
  return (
    <Component
      ref={ref as Ref<HTMLDivElement>}
      className={`${visible ? 'animate-rise' : 'opacity-0'} ${className}`}
      style={visible && delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Component>
  );
}
