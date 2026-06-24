"use client";

import { useEffect } from "react";

import { useRouter } from "next/navigation";

/**
 * Periodically re-runs the page's server components via router.refresh(), so
 * server-rendered data (the memory count, sync state, recent notes, commit
 * graph) stays current on the always-on hub without a manual reload. Client
 * components like the 3D memory map keep their state across the refresh, so
 * only the server-rendered parts update.
 */
export function AutoRefresh({ interval = 20_000 }: { interval?: number }) {
  const router = useRouter();
  useEffect(() => {
    const tick = () => router.refresh();
    const id = setInterval(tick, interval);
    const onVisible = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [interval, router]);
  return null;
}
