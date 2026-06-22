"use client";

import { useEffect } from "react";

/** Register the service worker in the browser (production only). */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* registration is best-effort */
    });
  }, []);
  return null;
}
